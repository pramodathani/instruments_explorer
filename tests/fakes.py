"""Test doubles shared by the test modules."""

import datetime
import math
from collections.abc import Awaitable, Callable
from typing import Any

import pymongo.errors
import redis

from instruments_explorer.unified_broker_interface import exceptions


class FixedClock:
    """A clock that stays at a set moment until moved.

    Attributes:
        epoch: The moment the clock shows, in epoch seconds.
    """

    def __init__(self, epoch: float):
        """Creates the clock.

        Args:
            epoch (float): The moment the clock shows, in epoch seconds.
        """
        self.epoch = epoch

    def now(self) -> float:
        """Reads the set moment.

        Returns:
            float: The moment in epoch seconds.
        """
        return self.epoch

    def advance(self, seconds: float) -> None:
        """Moves the clock forward.

        Args:
            seconds (float): How far to move, in seconds.
        """
        self.epoch += seconds


class FakeStoreChecker:
    """A stand-in store checker that returns a prepared report.

    Attributes:
        name: The store's name.
        reachable: Whether the report says the store is reachable.
    """

    def __init__(self, name: str, reachable: bool):
        """Creates the stand-in.

        Args:
            name (str): The store's name.
            reachable (bool): Whether the report says the store is reachable.
        """
        self.name = name
        self.reachable = reachable

    async def check(self) -> dict[str, Any]:
        """Returns the prepared report.

        Returns:
            dict[str, Any]: {"name", "reachable", "detail"}.
        """
        return {
            'name': self.name,
            'reachable': self.reachable,
            'detail': 'prepared by the test',
        }


class FakeRedisReader:
    """A stand-in for RedisReader that holds hash fields in memory.

    Attributes:
        hashes: Hash contents by key and field, as parsed documents.
        streams: Stream entries waiting to be read, by key.
        hash_reads: Every many-field hash read made, as tuples (key, fields).
        failing: Whether every read raises a Redis error.
    """

    def __init__(self, hashes: dict[str, dict[str, Any]] | None = None):
        """Creates the reader.

        Args:
            hashes (dict[str, dict[str, Any]] | None): Hash contents by key and field, or None for empty.
        """
        if hashes is None:
            hashes = {}
        self.hashes = hashes
        self.streams = {}
        self.hash_reads = []
        self.failing = False

    async def hash_get_json(self, key: str, field: str) -> Any:
        """Reads one hash field.

        Args:
            key (str): The hash key.
            field (str): The field.

        Returns:
            Any: The stored document, or None.

        Raises:
            redis.ConnectionError: The reader is set to fail.
        """
        if self.failing:
            raise redis.ConnectionError('Redis is down in this test.')
        return self.hashes.get(key, {}).get(field)

    async def ping_milliseconds(self) -> float:
        """Pretends to ping Redis.

        Returns:
            float: A fixed round trip of 1.5 milliseconds.

        Raises:
            redis.ConnectionError: The reader is set to fail.
        """
        if self.failing:
            raise redis.ConnectionError('Redis is down in this test.')
        return 1.5

    async def hash_get_many_json(
        self,
        key: str,
        fields: list[str],
    ) -> dict[str, Any]:
        """Reads several hash fields.

        Args:
            key (str): The hash key.
            fields (list[str]): The fields.

        Returns:
            dict[str, Any]: The stored document of each field that exists.

        Raises:
            redis.ConnectionError: The reader is set to fail.
        """
        if self.failing:
            raise redis.ConnectionError('Redis is down in this test.')
        self.hash_reads.append((key, list(fields)))
        found = {}
        for field in fields:
            document = self.hashes.get(key, {}).get(field)
            if document is not None:
                found[field] = document
        return found

    async def stream_read(
        self,
        key: str,
        last_id: str,
        count: int,
        block_milliseconds: int,
    ) -> list[tuple[str, dict[str, str]]]:
        """Hands out the entries queued in streams, as XREAD would.

        Args:
            key (str): The stream key.
            last_id (str): Ignored; queued entries are handed out once.
            count (int): The most entries to return.
            block_milliseconds (int): Ignored.

        Returns:
            list[tuple[str, dict[str, str]]]: Queued entries, oldest first.

        Raises:
            redis.ConnectionError: The reader is set to fail.
        """
        del last_id
        del block_milliseconds
        if self.failing:
            raise redis.ConnectionError('Redis is down in this test.')
        queued = self.streams.get(key, [])
        handed_out = queued[:count]
        self.streams[key] = queued[count:]
        return handed_out

    def store_login(self, access_token: str, expires_at: str) -> None:
        """Stores UBI's login document, as UBI does after a connect.

        Args:
            access_token (str): The token.
            expires_at (str): The expiry in UBI's local-time format.
        """
        logins = self.hashes.setdefault('last_login', {})
        logins['unified_broker_interface'] = {
            'broker_name': 'unified_broker_interface',
            'access_token': access_token,
            'expires_at': expires_at,
        }


class FakeMongoReader:
    """A stand-in for MongoReader with fixed credentials and login.

    Attributes:
        credentials: The API key and secret.
        login: The stored login document, or None.
        failing: Whether every read raises a MongoDB error.
        credential_reads: How many times the credentials were read.
    """

    def __init__(
        self,
        login: dict[str, Any] | None = None,
    ):
        """Creates the reader.

        Args:
            login (dict[str, Any] | None): The stored login document, or None.
        """
        self.credentials = (
            'test-key',
            'test-secret',
        )
        self.login = login
        self.failing = False
        self.credential_reads = 0

    def api_credentials(self) -> tuple[str, str]:
        """Reads the API key and secret.

        Returns:
            tuple[str, str]: A tuple (api_key, api_secret).

        Raises:
            pymongo.errors.ServerSelectionTimeoutError: The reader is set to fail.
        """
        if self.failing:
            raise pymongo.errors.ServerSelectionTimeoutError('MongoDB is down.')
        self.credential_reads += 1
        return self.credentials

    def stored_login(self) -> dict[str, Any] | None:
        """Reads the stored login.

        Returns:
            dict[str, Any] | None: The login document, or None.

        Raises:
            pymongo.errors.ServerSelectionTimeoutError: The reader is set to fail.
        """
        if self.failing:
            raise pymongo.errors.ServerSelectionTimeoutError('MongoDB is down.')
        return self.login


TODAY_EPOCH = datetime.datetime(2026, 9, 26, 10, 0).timestamp()  # noqa: DTZ001
NIFTY_ID = '00000000-0000-5000-8000-000000000001'
RELIANCE_NSE_ID = '00000000-0000-5000-8000-000000000002'


class CatalogueMaker:
    """Writes UBI identity documents for a small made-up catalogue."""

    def identity(
        self,
        instrument_id: str,
        exchange: str,
        segment: str,
        shape: str,
        symbol: str | None = None,
        underlying_symbol: str | None = None,
        expiry_date: str | None = None,
        strike_price: float | None = None,
        option_type: str | None = None,
    ) -> dict[str, Any]:
        """Writes one identity document.

        Args:
            instrument_id (str): The instrument id.
            exchange (str): The exchange.
            segment (str): The prefixed segment.
            shape (str): "security", "future" or "option".
            symbol (str | None): The symbol, for a security.
            underlying_symbol (str | None): The underlying, for a derivative.
            expiry_date (str | None): The expiry, for a derivative.
            strike_price (float | None): The strike, for an option.
            option_type (str | None): "CE" or "PE", for an option.

        Returns:
            dict[str, Any]: The identity document.
        """
        return {
            'instrument_id': instrument_id,
            'exchange': exchange,
            'segment': segment,
            'shape': shape,
            'symbol': symbol,
            'underlying_symbol': underlying_symbol,
            'expiry_date': expiry_date,
            'strike_price': strike_price,
            'option_type': option_type,
        }

    def catalogue(self) -> list[dict[str, Any]]:
        """Writes the whole made-up catalogue.

        Returns:
            list[dict[str, Any]]: Eleven identity documents, one of them for an option that expired before today.
        """
        return [
            self.identity(
                NIFTY_ID,
                'nse',
                'nse_equity_indices',
                'security',
                symbol='NIFTY',
            ),
            self.identity(
                RELIANCE_NSE_ID,
                'nse',
                'nse_equities',
                'security',
                symbol='RELIANCE',
            ),
            self.identity(
                'id-reliance-bse',
                'bse',
                'bse_equities',
                'security',
                symbol='RELIANCE',
            ),
            self.identity(
                'id-reliance-future',
                'nse',
                'nse_equity_futures',
                'future',
                underlying_symbol='RELIANCE',
                expiry_date='2026-10-27',
            ),
            self.identity(
                'id-nifty-future',
                'nse',
                'nse_equity_index_futures',
                'future',
                underlying_symbol='NIFTY',
                expiry_date='2026-09-29',
            ),
            self.identity(
                'id-nifty-25000-ce',
                'nse',
                'nse_equity_index_options',
                'option',
                underlying_symbol='NIFTY',
                expiry_date='2026-09-29',
                strike_price=25000.0,
                option_type='CE',
            ),
            self.identity(
                'id-nifty-25000-pe',
                'nse',
                'nse_equity_index_options',
                'option',
                underlying_symbol='NIFTY',
                expiry_date='2026-09-29',
                strike_price=25000.0,
                option_type='PE',
            ),
            self.identity(
                'id-nifty-26000-ce-october',
                'nse',
                'nse_equity_index_options',
                'option',
                underlying_symbol='NIFTY',
                expiry_date='2026-10-27',
                strike_price=26000.0,
                option_type='CE',
            ),
            self.identity(
                'id-nifty-expired',
                'nse',
                'nse_equity_index_options',
                'option',
                underlying_symbol='NIFTY',
                expiry_date='2026-09-22',
                strike_price=25000.0,
                option_type='CE',
            ),
            self.identity(
                'id-gold-future',
                'mcx',
                'mcx_commodity_futures',
                'future',
                underlying_symbol='GOLD',
                expiry_date='2026-10-05',
            ),
            self.identity(
                'id-niftybees',
                'nse',
                'nse_exchange_traded_funds',
                'security',
                symbol='NIFTYBEES',
            ),
        ]


class FakeCatalogueClient:
    """A stand-in for UnifiedBrokerInterfaceClient serving a prepared catalogue, details and quotes.

    Attributes:
        documents: The identity documents the master streams.
        mapping_date: The mapping date of the catalogue.
        details_by_id: Details documents by instrument id.
        additional_by_id: Additional details documents by instrument id.
        quotes_by_id: Quote documents by instrument id.
        prices_by_id: Prices documents by instrument id.
        price_requests: The (instrument id, interval, days, adjusted) of every prices call.
        failure: An error every per-instrument call raises, or None.
        master_downloads: How many times the master was streamed.
    """

    def __init__(
        self,
        documents: list[dict[str, Any]],
        mapping_date: str = '2026-09-25',
    ):
        """Creates the client.

        Args:
            documents (list[dict[str, Any]]): The identity documents the master streams.
            mapping_date (str): The mapping date of the catalogue.
        """
        self.documents = documents
        self.mapping_date = mapping_date
        self.details_by_id = {}
        self.additional_by_id = {}
        self.quotes_by_id = {}
        self.prices_by_id = {}
        self.price_requests = []
        self.failure = None
        self.master_downloads = 0

    async def greeting(self) -> dict[str, str]:
        """Returns UBI's welcome.

        Returns:
            dict[str, str]: A welcome message.
        """
        return {
            'message': 'welcome',
        }

    async def instrument_segments(self) -> dict[str, Any]:
        """Returns the mapping date.

        Returns:
            dict[str, Any]: A segments document with only the mapping date.
        """
        return {
            'mapping_date': self.mapping_date,
            'segments': [],
        }

    async def download_master(
        self,
        handle_batch: Callable[[list[dict[str, Any]]], Awaitable[None]],
        batch_size: int = 5000,
    ) -> str:
        """Hands the catalogue on in batches.

        Args:
            handle_batch (Callable[[list[dict[str, Any]]], Awaitable[None]]): Called with each batch.
            batch_size (int): How many documents each batch holds.

        Returns:
            str: The mapping date.
        """
        self.master_downloads += 1
        for start in range(0, len(self.documents), batch_size):
            await handle_batch(self.documents[start : start + batch_size])
        return self.mapping_date

    async def instrument_details(self, instrument_id: str) -> Any:
        """Returns prepared details.

        Args:
            instrument_id (str): The instrument id.

        Returns:
            Any: The details document.

        Raises:
            UnifiedBrokerInterfaceError: The prepared failure, or NotFoundError for an unknown id.
        """
        return self._lookup(self.details_by_id, instrument_id)

    async def additional_details(self, instrument_id: str) -> Any:
        """Returns prepared additional details.

        Args:
            instrument_id (str): The instrument id.

        Returns:
            Any: The additional details document.

        Raises:
            UnifiedBrokerInterfaceError: The prepared failure, or NotFoundError for an unknown id.
        """
        return self._lookup(self.additional_by_id, instrument_id)

    async def quote(self, instrument_id: str) -> Any:
        """Returns a prepared quote.

        Args:
            instrument_id (str): The instrument id.

        Returns:
            Any: The quote document.

        Raises:
            UnifiedBrokerInterfaceError: The prepared failure, or NotFoundError for an unknown id.
        """
        return self._lookup(self.quotes_by_id, instrument_id)

    async def prices(
        self,
        instrument_id: str,
        interval: str,
        days: int,
        adjusted: bool,
    ) -> Any:
        """Returns a prepared prices document and records the request.

        Args:
            instrument_id (str): The instrument id.
            interval (str): The candle interval.
            days (int): How many days back.
            adjusted (bool): Whether adjusted prices were asked for.

        Returns:
            Any: The prices document.

        Raises:
            UnifiedBrokerInterfaceError: The prepared failure, or NotFoundError for an unknown id.
        """
        self.price_requests.append(
            (
                instrument_id,
                interval,
                days,
                adjusted,
            )
        )
        return self._lookup(self.prices_by_id, instrument_id)

    def _lookup(self, documents: dict[str, Any], instrument_id: str) -> Any:
        """Finds a prepared document or raises the prepared failure.

        Args:
            documents (dict[str, Any]): Documents by instrument id.
            instrument_id (str): The instrument id.

        Returns:
            Any: The document.

        Raises:
            UnifiedBrokerInterfaceError: The prepared failure, or NotFoundError for an unknown id.
        """
        if self.failure is not None:
            raise self.failure
        if instrument_id not in documents:
            raise exceptions.NotFoundError(
                f'no instrument {instrument_id} is mapped on {self.mapping_date}',
                status_code=404,
            )
        return documents[instrument_id]


class RecordingSocket:
    """A stand-in WebSocket that records what is sent.

    Attributes:
        sent: The messages sent, in order.
        closed_with: The close code, or None while open.
    """

    def __init__(self):
        """Creates the socket."""
        self.sent = []
        self.closed_with = None

    async def send_json(self, data: Any) -> None:
        """Records a message.

        Args:
            data (Any): The message.
        """
        self.sent.append(data)

    async def close(self, code: int = 1000) -> None:
        """Records the close.

        Args:
            code (int): The close code.
        """
        self.closed_with = code


class PricesMaker:
    """Writes UBI prices documents with made-up candles."""

    def document(
        self,
        count: int,
        with_volume: bool = True,
    ) -> dict[str, Any]:
        """Writes daily candles whose close follows a slow wave around 1000.

        Args:
            count (int): How many candles to write.
            with_volume (bool): Whether candles have volume, or zero as for an index.

        Returns:
            dict[str, Any]: A prices document with "columns" and "candles", oldest first.
        """
        start = datetime.datetime(
            2025,
            1,
            1,
            tzinfo=datetime.UTC,
        )
        candles = []
        for index in range(count):
            moment = start + datetime.timedelta(days=index)
            close = 1000 + 50 * math.sin(index / 7) + index * 0.5
            candles.append(
                [
                    moment.isoformat(),
                    close - 2,
                    close + 6,
                    close - 7,
                    close,
                    1000 + index * 10 if with_volume else 0,
                    None,
                ]
            )
        return {
            'interval': 'day',
            'price_basis': 'adjusted',
            'adjustable': True,
            'source': 'database',
            'columns': [
                'time',
                'open',
                'high',
                'low',
                'close',
                'volume',
                'oi',
            ],
            'candles': candles,
        }
