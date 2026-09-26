"""Finds the access token for UBI's REST API without fighting other clients over it.

UBI issues one access token for its whole REST API, and every connect replaces it, which logs out every other client, such as tradingmachine. The provider therefore uses whatever token UBI has stored, and connects only when no usable token exists.

Typical usage example:

  token = await provider.current_token()
  ...
  token = await provider.token_after_refusal(token)
"""

import asyncio
import logging

import httpx
import pymongo.errors
import redis

from instruments_explorer.unified_broker_interface import exceptions
from instruments_explorer.unified_broker_interface import login_document
from instruments_explorer.unified_broker_interface import mongo_reader
from instruments_explorer.unified_broker_interface import redis_reader
from instruments_explorer.unified_broker_interface import response_reader
from instruments_explorer.utilities import clock

_LOGGER = logging.getLogger(__name__)
_LOGIN_HASH = 'last_login'
_APPLICATION_FIELD = 'unified_broker_interface'


class AccessTokenProvider:
    """Reads UBI's stored access token and connects only when there is none.

    Attributes:
        may_connect: Whether this process may call UBI's connect route.
        connect_cooldown_seconds: The shortest time between two connect attempts, in seconds.
        expiry_margin_seconds: How long a stored token must still be valid for to be used, in seconds.
        connect_count: How many connects this provider has made.
        connect_listener: Called with a description after every successful connect, such as a logger, or None.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        login_redis_reader: redis_reader.RedisReader,
        login_mongo_reader: mongo_reader.MongoReader,
        time_source: clock.SystemClock,
        may_connect: bool,
        connect_cooldown_seconds: float = 60.0,
        expiry_margin_seconds: float = 30.0,
    ):
        """Creates the provider.

        Args:
            http_client (httpx.AsyncClient): The client whose base URL is UBI's REST API.
            login_redis_reader (redis_reader.RedisReader): Reads the stored login from UBI's Redis.
            login_mongo_reader (mongo_reader.MongoReader): Reads the stored login and the API key and secret from UBI's MongoDB.
            time_source (clock.SystemClock): The source of the current time.
            may_connect (bool): Whether this process may call UBI's connect route.
            connect_cooldown_seconds (float): The shortest time between two connect attempts, in seconds.
            expiry_margin_seconds (float): How long a stored token must still be valid for to be used, in seconds.
        """
        self.may_connect = may_connect
        self.connect_cooldown_seconds = connect_cooldown_seconds
        self.expiry_margin_seconds = expiry_margin_seconds
        self.connect_count = 0
        self.connect_listener = None
        self._http_client = http_client
        self._redis_reader = login_redis_reader
        self._mongo_reader = login_mongo_reader
        self._time_source = time_source
        self._response_reader = response_reader.ResponseReader()
        self._lock = asyncio.Lock()
        self._last_connect_attempt_at = None

    async def current_token(self) -> str:
        """Finds a token to send with a request.

        Returns:
            str: UBI's stored token when it is usable, otherwise a token from a new connect.

        Raises:
            AuthenticationError: No usable token is stored and connecting is not allowed, is cooling down, or was refused.
            UnreachableError: Neither Redis nor MongoDB could be read, or UBI could not be reached to connect.
            ServerError: UBI answered the connect without a token.
            ValueError: UBI's API key or secret is missing from MongoDB.
        """
        async with self._lock:
            stored_token = await self._usable_stored_token(None)
            if stored_token is not None:
                return stored_token
            return await self._connect()

    async def token_after_refusal(self, refused_token: str) -> str:
        """Finds a token to retry with after UBI refused one.

        When another client has connected since the refused token was read, UBI already stores a newer token, and it is used without connecting.

        Args:
            refused_token (str): The token UBI answered 401 to.

        Returns:
            str: A newer stored token when there is one, otherwise a token from a new connect.

        Raises:
            AuthenticationError: No newer token is stored and connecting is not allowed, is cooling down, or was refused.
            UnreachableError: Neither Redis nor MongoDB could be read, or UBI could not be reached to connect.
            ServerError: UBI answered the connect without a token.
            ValueError: UBI's API key or secret is missing from MongoDB.
        """
        async with self._lock:
            stored_token = await self._usable_stored_token(refused_token)
            if stored_token is not None:
                return stored_token
            return await self._connect()

    async def stored_login(self) -> login_document.LoginDocument | None:
        """Reads UBI's stored login, from Redis first and MongoDB second.

        Returns:
            LoginDocument | None: The stored login, or None when neither store has one.

        Raises:
            UnreachableError: Redis had no readable login and MongoDB could not be read.
        """
        try:
            document = await self._redis_reader.hash_get_json(
                _LOGIN_HASH,
                _APPLICATION_FIELD,
            )
        except (redis.RedisError, ValueError) as error:
            _LOGGER.warning(
                'Could not read the UBI login from Redis: %s',
                error,
            )
            document = None
        if document is None:
            try:
                document = await asyncio.to_thread(
                    self._mongo_reader.stored_login
                )
            except pymongo.errors.PyMongoError as error:
                raise exceptions.UnreachableError(
                    'UBI Redis had no readable login and UBI MongoDB could not be read, so the current access token is unknown.'
                ) from error
        if document is None:
            return None
        return login_document.LoginDocument.from_document(document)

    async def _usable_stored_token(
        self, excluded_token: str | None
    ) -> str | None:
        """Finds the stored token when it is usable and not the excluded one.

        The caller must hold the lock.

        Args:
            excluded_token (str | None): A token known to be refused, or None.

        Returns:
            str | None: The stored token, or None when there is no usable one.

        Raises:
            UnreachableError: Neither Redis nor MongoDB could be read.
        """
        login = await self.stored_login()
        if login is None:
            return None
        now = self._time_source.now()
        if not login.is_usable(now, self.expiry_margin_seconds):
            return None
        if login.access_token == excluded_token:
            return None
        return login.access_token

    async def _connect(self) -> str:
        """Exchanges UBI's API key and secret for a new token.

        The caller must hold the lock.

        Returns:
            str: The new token.

        Raises:
            AuthenticationError: Connecting is not allowed, is cooling down, or was refused.
            UnreachableError: UBI could not be reached.
            ServerError: UBI answered without a token.
            ValueError: UBI's API key or secret is missing from MongoDB.
        """
        if not self.may_connect:
            raise exceptions.AuthenticationError(
                'UBI has no usable access token stored, and this process is not allowed to connect for one.'
            )
        now = self._time_source.now()
        if self._last_connect_attempt_at is not None:
            elapsed = now - self._last_connect_attempt_at
            if elapsed < self.connect_cooldown_seconds:
                raise exceptions.AuthenticationError(
                    f'UBI refused the access token again {elapsed:.0f} seconds after the last connect; instruments_explorer waits {self.connect_cooldown_seconds:.0f} seconds between connects.'
                )
        self._last_connect_attempt_at = now
        api_key, api_secret = await asyncio.to_thread(
            self._mongo_reader.api_credentials
        )
        try:
            response = await self._http_client.post(
                '/api/session/connect',
                headers={
                    'api-key': api_key,
                    'api-secret': api_secret,
                },
            )
        except httpx.RequestError as error:
            raise exceptions.UnreachableError(
                f'Could not reach UBI to connect: {error}'
            ) from error
        body = self._response_reader.read(response)
        if not isinstance(body, dict):
            body = {}
        login = login_document.LoginDocument.from_document(body)
        if not login.access_token:
            raise exceptions.ServerError(
                'UBI answered the connect without an access token.',
                status_code=response.status_code,
            )
        self.connect_count += 1
        if self.connect_listener is not None:
            self.connect_listener(
                f'Connected to UBI for a new access token expiring {login.expires_at_text}; other UBI clients were logged out.'
            )
        _LOGGER.warning(
            'Connected to UBI for a new access token expiring %s; this ends the session of any other UBI client, such as tradingmachine.',
            login.expires_at_text,
        )
        return login.access_token
