"""Test doubles shared by the test modules."""

import copy
import datetime
import math
import types
from collections.abc import Awaitable, Callable
from typing import Any, Self

import pymongo.errors
import redis
from anthropic import _models as anthropic_models
from anthropic.types.beta import parsed_beta_message

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


class FakeSnapshotReader:
    """A stand-in for QuoteSnapshotReader serving prepared quotes.

    Attributes:
        quotes: Unified quotes by instrument id.
    """

    def __init__(self, quotes: dict[str, Any] | None = None):
        """Creates the reader.

        Args:
            quotes (dict[str, Any] | None): Unified quotes by instrument id, or None for none.
        """
        if quotes is None:
            quotes = {}
        self.quotes = quotes

    async def read(self, instrument_ids: list[str]) -> dict[str, Any]:
        """Returns the prepared quotes of the instruments asked for.

        Args:
            instrument_ids (list[str]): The instruments.

        Returns:
            dict[str, Any]: The quotes that exist, by instrument id.
        """
        found = {}
        for instrument_id in instrument_ids:
            if instrument_id in self.quotes:
                found[instrument_id] = self.quotes[instrument_id]
        return found


class FakeCursor:
    """A stand-in for a pymongo async cursor over prepared documents.

    Attributes:
        documents: The matching documents, in their current order.
    """

    def __init__(self, documents: list[dict[str, Any]]):
        """Creates the cursor.

        Args:
            documents (list[dict[str, Any]]): The matching documents.
        """
        self.documents = documents

    def sort(self, field: str, direction: int) -> Self:
        """Orders the documents by one field, missing values first.

        Args:
            field (str): The field.
            direction (int): 1 for ascending, -1 for descending.

        Returns:
            Self: This cursor.
        """
        self.documents.sort(
            key=lambda document: (
                document.get(field) is not None,
                document.get(field) or 0,
            ),
            reverse=direction < 0,
        )
        return self

    def limit(self, count: int) -> Self:
        """Keeps the first documents.

        Args:
            count (int): How many to keep.

        Returns:
            Self: This cursor.
        """
        self.documents = self.documents[:count]
        return self

    def __aiter__(self) -> Any:
        """Starts asynchronous iteration.

        Returns:
            Any: An asynchronous iterator over copies of the documents.
        """
        return self._iterate()

    async def _iterate(self) -> Any:
        """Yields copies of the documents.

        Yields:
            dict[str, Any]: Each document.
        """
        for document in self.documents:
            yield dict(document)


class FakeCollection:
    """A stand-in for a pymongo async collection supporting the operations the repositories use.

    Filters support equality, "$exists", a "^prefix" "$regex" and "$or". Updates support "$set" with dotted keys and "$inc".

    Attributes:
        documents: The stored documents by _id.
    """

    def __init__(self):
        """Creates an empty collection."""
        self.documents = {}

    async def create_index(self, field: str) -> None:
        """Pretends to create an index.

        Args:
            field (str): The field.
        """
        del field

    async def update_one(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        upsert: bool = False,
    ) -> None:
        """Sets fields on the first matching document, creating it when asked.

        Args:
            query (dict[str, Any]): The filter.
            update (dict[str, Any]): An update with "$set" and optionally "$inc".
            upsert (bool): Whether to create a missing document.
        """
        document = self._first(query)
        if document is None:
            if not upsert:
                return
            document = {
                '_id': query.get('_id'),
            }
            self.documents[document['_id']] = document
        for key, value in update.get('$set', {}).items():
            target = document
            parts = key.split('.')
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = value
        for key, value in update.get('$inc', {}).items():
            document[key] = document.get(key, 0) + value

    async def insert_one(self, document: dict[str, Any]) -> None:
        """Stores a new document under its _id.

        Args:
            document (dict[str, Any]): The document, with "_id".

        Raises:
            KeyError: A document with that _id already exists.
        """
        if document['_id'] in self.documents:
            raise KeyError(f'Duplicate _id: {document["_id"]!r}')
        self.documents[document['_id']] = dict(document)

    async def delete_one(self, query: dict[str, Any]) -> None:
        """Removes the first matching document.

        Args:
            query (dict[str, Any]): The filter.
        """
        document = self._first(query)
        if document is not None:
            del self.documents[document['_id']]

    async def delete_many(self, query: dict[str, Any]) -> None:
        """Removes every matching document.

        Args:
            query (dict[str, Any]): The filter.
        """
        doomed = []
        for key, document in self.documents.items():
            if self._matches(document, query):
                doomed.append(key)
        for key in doomed:
            del self.documents[key]

    async def replace_one(
        self,
        query: dict[str, Any],
        replacement: dict[str, Any],
        upsert: bool = False,
    ) -> None:
        """Replaces a document by _id.

        Args:
            query (dict[str, Any]): A filter on _id.
            replacement (dict[str, Any]): The new document.
            upsert (bool): Whether to create a missing document.
        """
        if query['_id'] in self.documents or upsert:
            self.documents[query['_id']] = dict(replacement)

    async def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        """Finds the first matching document.

        Args:
            query (dict[str, Any]): The filter.

        Returns:
            dict[str, Any] | None: A copy of the document, or None.
        """
        document = self._first(query)
        return dict(document) if document is not None else None

    def find(
        self,
        query: dict[str, Any],
        projection: dict[str, int] | None = None,
    ) -> FakeCursor:
        """Finds every matching document.

        Args:
            query (dict[str, Any]): The filter.
            projection (dict[str, int] | None): Fields set to 0 are left out.

        Returns:
            FakeCursor: A cursor over copies of the matches.
        """
        found = []
        for document in self.documents.values():
            if self._matches(document, query):
                copy = dict(document)
                for field, included in (projection or {}).items():
                    if not included:
                        copy.pop(field, None)
                found.append(copy)
        return FakeCursor(found)

    async def count_documents(self, query: dict[str, Any]) -> int:
        """Counts matching documents.

        Args:
            query (dict[str, Any]): The filter.

        Returns:
            int: The count.
        """
        count = 0
        for document in self.documents.values():
            if self._matches(document, query):
                count += 1
        return count

    def _first(self, query: dict[str, Any]) -> dict[str, Any] | None:
        """Finds the stored first matching document.

        Args:
            query (dict[str, Any]): The filter.

        Returns:
            dict[str, Any] | None: The stored document itself, or None.
        """
        for document in self.documents.values():
            if self._matches(document, query):
                return document
        return None

    def _matches(self, document: dict[str, Any], query: dict[str, Any]) -> bool:
        """Checks a document against a filter.

        Args:
            document (dict[str, Any]): The document.
            query (dict[str, Any]): The filter.

        Returns:
            bool: True when every condition holds.
        """
        for field, condition in query.items():
            if field == '$or':
                if not any(self._matches(document, part) for part in condition):
                    return False
                continue
            value = document.get(field)
            if isinstance(condition, dict):
                if (
                    '$exists' in condition
                    and (field in document) != condition['$exists']
                ):
                    return False
                if '$regex' in condition:
                    prefix = condition['$regex'].lstrip('^').replace('\\\\', '')
                    if not isinstance(value, str) or not value.startswith(
                        prefix
                    ):
                        return False
            elif value != condition:
                return False
        return True


class FakeDatabase:
    """A stand-in for a pymongo async database holding fake collections.

    Attributes:
        collections: The collections by name.
    """

    def __init__(self):
        """Creates an empty database."""
        self.collections = {}

    def __getitem__(self, name: str) -> FakeCollection:
        """Gives a collection, creating it on first use.

        Args:
            name (str): The collection's name.

        Returns:
            FakeCollection: The collection.
        """
        return self.collections.setdefault(name, FakeCollection())


class FakeVectorStore:
    """A stand-in for VectorStore that matches chunks by shared words instead of embeddings.

    Attributes:
        chunks: Stored chunks as (id, text, metadata).
    """

    def __init__(self):
        """Creates an empty store."""
        self.chunks = []

    def add(
        self,
        document_id: str,
        chunks: list[str],
        metadata: dict[str, Any],
    ) -> int:
        """Replaces a document's chunks.

        Args:
            document_id (str): The document's id.
            chunks (list[str]): The chunks.
            metadata (dict[str, Any]): Fields stored with each chunk.

        Returns:
            int: The number of chunks stored.
        """
        kept = []
        for chunk in self.chunks:
            if chunk[2]['document_id'] != document_id:
                kept.append(chunk)
        self.chunks = kept
        for position, text in enumerate(chunks):
            stored = dict(metadata)
            stored['document_id'] = document_id
            self.chunks.append((f'{document_id}:{position}', text, stored))
        return len(chunks)

    def query(
        self,
        text: str,
        company_key: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Ranks chunks by how many of the question's words they share.

        Args:
            text (str): The question.
            company_key (str | None): Only this company's chunks, or all.
            limit (int): The largest number of chunks.

        Returns:
            list[dict[str, Any]]: {"text", "distance", "metadata"} per chunk, best first.
        """
        words = set(text.lower().split())
        scored = []
        for _, chunk_text, metadata in self.chunks:
            if (
                company_key is not None
                and metadata.get('company_key') != company_key
            ):
                continue
            shared = len(words & set(chunk_text.lower().split()))
            if shared:
                scored.append((shared, chunk_text, metadata))
        scored.sort(key=lambda item: -item[0])
        hits = []
        for shared, chunk_text, metadata in scored[:limit]:
            hits.append(
                {
                    'text': chunk_text,
                    'distance': 1.0 / (1 + shared),
                    'metadata': metadata,
                }
            )
        return hits

    def count(self) -> int:
        """Counts the stored chunks.

        Returns:
            int: The number of chunks.
        """
        return len(self.chunks)


class FakeFetcher:
    """A stand-in fetcher that returns a prepared result or raises a prepared error.

    Attributes:
        key: The fetcher's key.
        label: The fetcher's label.
        description: A description.
        news: Whether it counts as a news source.
        result: The FetchResult to return.
        error: An error to raise instead, or None.
        is_available: Whether it reports itself available.
        calls: The companies it was asked about.
    """

    def __init__(
        self,
        key: str,
        result: Any,
        error: Exception | None = None,
        is_available: bool = True,
        news: bool = False,
    ):
        """Creates the fetcher.

        Args:
            key (str): The fetcher's key.
            result (Any): The FetchResult to return.
            error (Exception | None): An error to raise instead, or None.
            is_available (bool): Whether it reports itself available.
            news (bool): Whether it counts as a news source.
        """
        self.key = key
        self.label = key.title()
        self.description = f'The {key} stand-in.'
        self.news = news
        self.result = result
        self.error = error
        self.is_available = is_available
        self.calls = []

    def available(self) -> tuple[bool, str]:
        """Reports the prepared availability.

        Returns:
            tuple[bool, str]: Whether it can run, and why not.
        """
        if self.is_available:
            return True, ''
        return False, 'Switched off in this test.'

    def describe(self) -> dict[str, Any]:
        """Describes the fetcher.

        Returns:
            dict[str, Any]: Its key, label and availability.
        """
        available, reason = self.available()
        return {
            'key': self.key,
            'label': self.label,
            'description': self.description,
            'news': self.news,
            'available': available,
            'reason': reason,
        }

    async def fetch(self, company: Any) -> Any:
        """Returns the prepared result or raises the prepared error.

        Args:
            company (Any): The company asked about.

        Returns:
            Any: The prepared FetchResult.

        Raises:
            Exception: The prepared error.
        """
        self.calls.append(company)
        if self.error is not None:
            raise self.error
        return self.result


class FakeTurn:
    """One prepared answer from the fake Claude client: the stream events and the finished message.

    Attributes:
        content: The answer's content blocks as API dictionaries.
        stop_reason: Why the answer stopped.
        usage: The answer's token counts.
        fails_with: An exception the stream raises instead of answering, or None.
    """

    def __init__(
        self,
        content: list[dict[str, Any]],
        stop_reason: str,
        usage: dict[str, int] | None = None,
        fails_with: Exception | None = None,
    ):
        """Prepares the answer.

        Args:
            content (list[dict[str, Any]]): The content blocks as API dictionaries.
            stop_reason (str): Why the answer stopped, such as "end_turn" or "tool_use".
            usage (dict[str, int] | None): Token counts, or None for small defaults.
            fails_with (Exception | None): An exception the stream raises instead of answering, or None.
        """
        self.content = content
        self.stop_reason = stop_reason
        if usage is None:
            usage = {
                'input_tokens': 100,
                'output_tokens': 20,
                'cache_read_input_tokens': 0,
                'cache_creation_input_tokens': 0,
            }
        self.usage = usage
        self.fails_with = fails_with

    def events(self) -> list[Any]:
        """Makes the stream events the SDK would give for this answer.

        Returns:
            list[Any]: Block starts, text and thinking deltas.
        """
        events = []
        for block in self.content:
            events.append(
                types.SimpleNamespace(
                    type='content_block_start',
                    content_block=types.SimpleNamespace(**block),
                )
            )
            if block['type'] == 'text':
                events.append(
                    types.SimpleNamespace(
                        type='text',
                        text=block['text'],
                    )
                )
            if block['type'] == 'thinking':
                events.append(
                    types.SimpleNamespace(
                        type='thinking',
                        thinking=block['thinking'],
                    )
                )
        return events

    def message(self) -> Any:
        """Builds the finished message with the SDK's own types.

        Returns:
            Any: A ParsedBetaMessage.
        """
        return anthropic_models.construct_type(
            type_=parsed_beta_message.ParsedBetaMessage,
            value={
                'id': 'msg_fake',
                'type': 'message',
                'role': 'assistant',
                'model': 'claude-opus-5-5',
                'content': self.content,
                'stop_reason': self.stop_reason,
                'stop_sequence': None,
                'usage': self.usage,
            },
        )


class FakeStream:
    """A stand-in for the SDK's async message stream."""

    def __init__(self, turn: FakeTurn):
        """Keeps the answer to replay.

        Args:
            turn (FakeTurn): The answer.
        """
        self._turn = turn

    async def __aenter__(self) -> Self:
        """Opens the stream.

        Returns:
            Self: The stream.
        """
        return self

    async def __aexit__(self, *details: object) -> None:
        """Closes the stream.

        Args:
            *details (Any): The exception details, ignored.
        """
        del details

    def __aiter__(self) -> Any:
        """Starts replaying the events.

        Returns:
            Any: An asynchronous iterator over the events.
        """
        return self._replay()

    async def _replay(self) -> Any:
        """Yields the events, or raises the prepared failure.

        Yields:
            Any: Each event.

        Raises:
            Exception: The prepared failure.
        """
        if self._turn.fails_with is not None:
            raise self._turn.fails_with
        for event in self._turn.events():
            yield event

    async def get_final_message(self) -> Any:
        """Gives the finished message.

        Returns:
            Any: The message.
        """
        return self._turn.message()


class FakeClaudeMessages:
    """A stand-in for client.beta.messages that replays prepared answers in order.

    Attributes:
        turns: The answers still to give.
        requests: The keyword arguments of every stream request, in order.
    """

    def __init__(self, turns: list[FakeTurn]):
        """Keeps the answers.

        Args:
            turns (list[FakeTurn]): The answers, in order.
        """
        self.turns = list(turns)
        self.requests = []

    def stream(self, **request: Any) -> FakeStream:
        """Records a request and replays the next answer.

        Args:
            **request (Any): The request's keyword arguments.

        Returns:
            FakeStream: The stream of the next answer.
        """
        self.requests.append(copy.deepcopy(request))
        return FakeStream(self.turns.pop(0))


class FakeClaudeClient:
    """A stand-in for anthropic.AsyncAnthropic with only beta.messages.stream.

    Attributes:
        beta: Holds messages.
        messages: The fake messages resource, for inspecting requests.
    """

    def __init__(self, turns: list[FakeTurn]):
        """Prepares the answers.

        Args:
            turns (list[FakeTurn]): The answers, in order.
        """
        self.messages = FakeClaudeMessages(turns)
        self.beta = types.SimpleNamespace(messages=self.messages)

    async def close(self) -> None:
        """Does nothing, as there is no connection."""
