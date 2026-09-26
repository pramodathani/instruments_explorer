"""Tests for finding UBI's access token without fighting other clients."""

import asyncio
import datetime

import httpx
import pytest

from instruments_explorer.unified_broker_interface import access_token_provider
from instruments_explorer.unified_broker_interface import exceptions
from tests import fakes

_START = datetime.datetime(2026, 9, 16, 10, 0, 0).timestamp()  # noqa: DTZ001
_TIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'


class _FakeUnifiedBrokerInterface:
    """A stand-in for UBI's connect route that stores each new token in Redis.

    Attributes:
        connect_requests: The connect requests received.
        status_code: The status to answer connects with.
    """

    def __init__(
        self,
        redis_reader: fakes.FakeRedisReader,
        time_source: fakes.FixedClock,
    ):
        """Creates the stand-in.

        Args:
            redis_reader (fakes.FakeRedisReader): The Redis the new token is stored in.
            time_source (fakes.FixedClock): The clock the expiry is based on.
        """
        self.redis_reader = redis_reader
        self.time_source = time_source
        self.connect_requests = []
        self.status_code = 200

    def handle(self, request: httpx.Request) -> httpx.Response:
        """Answers a request as UBI's connect route does.

        Args:
            request (httpx.Request): The request.

        Returns:
            httpx.Response: A new token, or an error for a refused connect.
        """
        self.connect_requests.append(request)
        if self.status_code != 200:
            return httpx.Response(
                self.status_code,
                json={
                    'error': 'Invalid API key or secret',
                },
            )
        token = f'connected-{len(self.connect_requests)}'
        expires_at = datetime.datetime.fromtimestamp(  # noqa: DTZ006
            self.time_source.now() + 86400
        ).strftime(_TIME_FORMAT)
        self.redis_reader.store_login(token, expires_at)
        return httpx.Response(
            200,
            json={
                'access-token': token,
                'expires_at': expires_at,
            },
        )


class TestAccessTokenProvider:
    """Tests for AccessTokenProvider."""

    def _expiry(self, time_source: fakes.FixedClock, seconds: float) -> str:
        """Writes an expiry some seconds from the clock's time, in UBI's format.

        Args:
            time_source (fakes.FixedClock): The clock.
            seconds (float): How far ahead, in seconds.

        Returns:
            str: The expiry text.
        """
        moment = datetime.datetime.fromtimestamp(  # noqa: DTZ006
            time_source.now() + seconds
        )
        return moment.strftime(_TIME_FORMAT)

    def _provider(
        self,
        redis_reader: fakes.FakeRedisReader,
        mongo_reader: fakes.FakeMongoReader,
        time_source: fakes.FixedClock,
        may_connect: bool = True,
    ) -> tuple[
        access_token_provider.AccessTokenProvider,
        _FakeUnifiedBrokerInterface,
    ]:
        """Builds a provider whose connects reach a stand-in for UBI.

        Args:
            redis_reader (fakes.FakeRedisReader): The Redis stand-in.
            mongo_reader (fakes.FakeMongoReader): The MongoDB stand-in.
            time_source (fakes.FixedClock): The clock.
            may_connect (bool): Whether the provider may connect.

        Returns:
            tuple[AccessTokenProvider, _FakeUnifiedBrokerInterface]: A tuple (provider, UBI stand-in).
        """
        unified_broker_interface = _FakeUnifiedBrokerInterface(
            redis_reader,
            time_source,
        )
        http_client = httpx.AsyncClient(
            base_url='http://ubi.test',
            transport=httpx.MockTransport(unified_broker_interface.handle),
        )
        provider = access_token_provider.AccessTokenProvider(
            http_client,
            redis_reader,
            mongo_reader,
            time_source,
            may_connect,
            connect_cooldown_seconds=60.0,
            expiry_margin_seconds=30.0,
        )
        return provider, unified_broker_interface

    def test_usable_stored_token_is_used_without_connecting(self) -> None:
        """Checks that a valid token in Redis is used and nothing connects."""
        time_source = fakes.FixedClock(_START)
        redis_reader = fakes.FakeRedisReader()
        redis_reader.store_login('stored', self._expiry(time_source, 3600))
        provider, unified_broker_interface = self._provider(
            redis_reader,
            fakes.FakeMongoReader(),
            time_source,
        )
        assert asyncio.run(provider.current_token()) == 'stored'
        assert unified_broker_interface.connect_requests == []
        assert provider.connect_count == 0

    def test_token_near_expiry_leads_to_a_connect(self) -> None:
        """Checks that a token expiring within the margin is replaced by connecting with the API key and secret, and the connect is reported to the listener."""
        time_source = fakes.FixedClock(_START)
        redis_reader = fakes.FakeRedisReader()
        redis_reader.store_login('stale', self._expiry(time_source, 10))
        provider, unified_broker_interface = self._provider(
            redis_reader,
            fakes.FakeMongoReader(),
            time_source,
        )
        descriptions = []
        provider.connect_listener = descriptions.append
        assert asyncio.run(provider.current_token()) == 'connected-1'
        assert len(descriptions) == 1
        assert 'other UBI clients were logged out' in descriptions[0]
        request = unified_broker_interface.connect_requests[0]
        assert request.url.path == '/api/session/connect'
        assert request.headers['api-key'] == 'test-key'
        assert request.headers['api-secret'] == 'test-secret'
        assert provider.connect_count == 1

    def test_mongodb_login_is_used_when_redis_has_none(self) -> None:
        """Checks that the MongoDB copy of the login is used when Redis has no field."""
        time_source = fakes.FixedClock(_START)
        mongo_reader = fakes.FakeMongoReader(
            {
                'access_token': 'from-mongo',
                'expires_at': self._expiry(time_source, 3600),
            }
        )
        provider, unified_broker_interface = self._provider(
            fakes.FakeRedisReader(),
            mongo_reader,
            time_source,
        )
        assert asyncio.run(provider.current_token()) == 'from-mongo'
        assert unified_broker_interface.connect_requests == []

    def test_redis_failure_falls_back_to_mongodb(self) -> None:
        """Checks that an unreachable Redis does not stop the MongoDB copy being used."""
        time_source = fakes.FixedClock(_START)
        redis_reader = fakes.FakeRedisReader()
        redis_reader.failing = True
        mongo_reader = fakes.FakeMongoReader(
            {
                'access_token': 'from-mongo',
                'expires_at': self._expiry(time_source, 3600),
            }
        )
        provider, _ = self._provider(redis_reader, mongo_reader, time_source)
        assert asyncio.run(provider.current_token()) == 'from-mongo'

    def test_unreadable_stores_never_lead_to_a_connect(self) -> None:
        """Checks that when neither store can be read, the provider refuses instead of connecting blindly.

        Raises:
            AssertionError: No error was raised.
        """
        time_source = fakes.FixedClock(_START)
        redis_reader = fakes.FakeRedisReader()
        redis_reader.failing = True
        mongo_reader = fakes.FakeMongoReader()
        mongo_reader.failing = True
        provider, unified_broker_interface = self._provider(
            redis_reader,
            mongo_reader,
            time_source,
        )
        with pytest.raises(exceptions.UnreachableError):
            asyncio.run(provider.current_token())
        assert unified_broker_interface.connect_requests == []

    def test_refusal_with_a_newer_stored_token_does_not_connect(self) -> None:
        """Checks that after a 401, a token another client obtained is adopted without connecting."""
        time_source = fakes.FixedClock(_START)
        redis_reader = fakes.FakeRedisReader()
        redis_reader.store_login('old', self._expiry(time_source, 3600))
        provider, unified_broker_interface = self._provider(
            redis_reader,
            fakes.FakeMongoReader(),
            time_source,
        )
        refused = asyncio.run(provider.current_token())
        redis_reader.store_login(
            'tradingmachine', self._expiry(time_source, 86400)
        )
        retry_token = asyncio.run(provider.token_after_refusal(refused))
        assert retry_token == 'tradingmachine'
        assert unified_broker_interface.connect_requests == []

    def test_refusal_of_the_stored_token_connects_once(self) -> None:
        """Checks that when UBI refuses the token it still stores, the provider connects once."""
        time_source = fakes.FixedClock(_START)
        redis_reader = fakes.FakeRedisReader()
        redis_reader.store_login('revoked', self._expiry(time_source, 3600))
        provider, unified_broker_interface = self._provider(
            redis_reader,
            fakes.FakeMongoReader(),
            time_source,
        )
        retry_token = asyncio.run(provider.token_after_refusal('revoked'))
        assert retry_token == 'connected-1'
        assert len(unified_broker_interface.connect_requests) == 1

    def test_second_refusal_within_the_cooldown_does_not_connect(self) -> None:
        """Checks that two refusals within a minute lead to one connect and then an error.

        Raises:
            AssertionError: No error was raised.
        """
        time_source = fakes.FixedClock(_START)
        redis_reader = fakes.FakeRedisReader()
        redis_reader.store_login('revoked', self._expiry(time_source, 3600))
        provider, unified_broker_interface = self._provider(
            redis_reader,
            fakes.FakeMongoReader(),
            time_source,
        )
        new_token = asyncio.run(provider.token_after_refusal('revoked'))
        time_source.advance(20)
        with pytest.raises(exceptions.AuthenticationError, match='waits 60'):
            asyncio.run(provider.token_after_refusal(new_token))
        assert len(unified_broker_interface.connect_requests) == 1

    def test_connect_is_allowed_again_after_the_cooldown(self) -> None:
        """Checks that a connect is allowed once the cooldown has passed."""
        time_source = fakes.FixedClock(_START)
        redis_reader = fakes.FakeRedisReader()
        redis_reader.store_login('revoked', self._expiry(time_source, 3600))
        provider, unified_broker_interface = self._provider(
            redis_reader,
            fakes.FakeMongoReader(),
            time_source,
        )
        new_token = asyncio.run(provider.token_after_refusal('revoked'))
        time_source.advance(61)
        asyncio.run(provider.token_after_refusal(new_token))
        assert len(unified_broker_interface.connect_requests) == 2

    def test_process_that_may_not_connect_raises(self) -> None:
        """Checks that a provider without permission to connect never calls connect.

        Raises:
            AssertionError: No error was raised.
        """
        time_source = fakes.FixedClock(_START)
        mongo_reader = fakes.FakeMongoReader()
        provider, unified_broker_interface = self._provider(
            fakes.FakeRedisReader(),
            mongo_reader,
            time_source,
            may_connect=False,
        )
        with pytest.raises(exceptions.AuthenticationError, match='not allowed'):
            asyncio.run(provider.current_token())
        assert unified_broker_interface.connect_requests == []
        assert mongo_reader.credential_reads == 0

    def test_refused_connect_raises_authentication_error(self) -> None:
        """Checks that a connect refused by UBI raises AuthenticationError with UBI's message.

        Raises:
            AssertionError: No error was raised.
        """
        time_source = fakes.FixedClock(_START)
        provider, unified_broker_interface = self._provider(
            fakes.FakeRedisReader(),
            fakes.FakeMongoReader(),
            time_source,
        )
        unified_broker_interface.status_code = 401
        with pytest.raises(
            exceptions.AuthenticationError,
            match='Invalid API key or secret',
        ):
            asyncio.run(provider.current_token())

    def test_concurrent_requests_share_one_connect(self) -> None:
        """Checks that requests arriving together without a token cause only one connect."""
        time_source = fakes.FixedClock(_START)
        redis_reader = fakes.FakeRedisReader()
        provider, unified_broker_interface = self._provider(
            redis_reader,
            fakes.FakeMongoReader(),
            time_source,
        )

        async def request_three_tokens() -> list[str]:
            """Asks for three tokens at once.

            Returns:
                list[str]: The three tokens.
            """
            return await asyncio.gather(
                provider.current_token(),
                provider.current_token(),
                provider.current_token(),
            )

        tokens = asyncio.run(request_three_tokens())
        assert tokens == [
            'connected-1',
            'connected-1',
            'connected-1',
        ]
        assert len(unified_broker_interface.connect_requests) == 1
