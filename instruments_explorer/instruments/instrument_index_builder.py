"""Builds the instrument search index from UBI's instrument master.

The index is one SQLite file per catalogue mapping date. Every instrument that has not expired is stored with its asset class, readable name and search words, and indexed for full-text search and for the explorer's filters.

The file is written under a temporary name and renamed into place only when complete, so a reader never sees a half-built index.

Typical usage example:

  builder = InstrumentIndexBuilder(client, Path('data/instruments'), clock)
  path, mapping_date = await builder.build()
"""

import asyncio
import datetime
import logging
import sqlite3
from pathlib import Path
from typing import Any

from instruments_explorer.instruments import asset_classifier
from instruments_explorer.instruments import instrument_namer
from instruments_explorer.instruments import search_text_builder
from instruments_explorer.unified_broker_interface import rest_client
from instruments_explorer.utilities import clock

_LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = '2'
_FILE_PREFIX = 'instruments-'
_FILE_SUFFIX = '.sqlite'

_SCHEMA = [
    """
    CREATE TABLE instruments (
        row_number INTEGER PRIMARY KEY,
        instrument_id TEXT NOT NULL UNIQUE,
        exchange TEXT NOT NULL,
        segment TEXT NOT NULL,
        bare_segment TEXT NOT NULL,
        asset_class TEXT NOT NULL,
        shape TEXT NOT NULL,
        is_index INTEGER NOT NULL,
        symbol TEXT,
        underlying_symbol TEXT,
        root_name TEXT NOT NULL,
        root_key TEXT NOT NULL,
        display_name TEXT NOT NULL,
        company_name TEXT,
        expiry_date TEXT,
        expiry_month TEXT,
        strike_price REAL,
        option_type TEXT,
        exchange_rank INTEGER NOT NULL,
        shape_rank INTEGER NOT NULL
    )
    """,
    """
    CREATE VIRTUAL TABLE instrument_search USING fts5(
        search_text,
        content='',
        tokenize='unicode61'
    )
    """,
    """
    CREATE TABLE index_details (
        name TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
]
_FINISHING_STATEMENTS = [
    'CREATE INDEX instruments_by_exchange ON instruments (exchange)',
    'CREATE INDEX instruments_by_asset_class ON instruments (asset_class)',
    'CREATE INDEX instruments_by_segment ON instruments (segment)',
    'CREATE INDEX instruments_by_shape ON instruments (shape)',
    'CREATE INDEX instruments_by_expiry_month ON instruments (expiry_month)',
    'CREATE INDEX instruments_by_underlying ON instruments (underlying_symbol, expiry_date, strike_price)',
    'CREATE INDEX instruments_by_root ON instruments (root_key)',
]
_INSERT_INSTRUMENT = """
    INSERT INTO instruments (
        row_number,
        instrument_id,
        exchange,
        segment,
        bare_segment,
        asset_class,
        shape,
        is_index,
        symbol,
        underlying_symbol,
        root_name,
        root_key,
        display_name,
        company_name,
        expiry_date,
        expiry_month,
        strike_price,
        option_type,
        exchange_rank,
        shape_rank
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
_INSERT_SEARCH_TEXT = (
    'INSERT INTO instrument_search (rowid, search_text) VALUES (?, ?)'
)


class InstrumentIndexBuilder:
    """Downloads UBI's catalogue and writes a search index file.

    Attributes:
        index_directory: The directory holding the index files.
        stored_count: How many instruments the build in progress has stored so far.
    """

    def __init__(
        self,
        client: rest_client.UnifiedBrokerInterfaceClient,
        index_directory: Path,
        time_source: clock.SystemClock,
    ):
        """Creates the builder.

        Args:
            client (rest_client.UnifiedBrokerInterfaceClient): Downloads the instrument master.
            index_directory (Path): The directory holding the index files.
            time_source (clock.SystemClock): The source of today's date.
        """
        self.index_directory = index_directory
        self.stored_count = 0
        self._client = client
        self._time_source = time_source
        self._classifier = asset_classifier.AssetClassifier()
        self._namer = instrument_namer.InstrumentNamer()
        self._text_builder = search_text_builder.SearchTextBuilder()
        self._seen_ids = set()
        self._company_names = {}

    def path_for(self, mapping_date: str) -> Path:
        """Finds the index file of a mapping date.

        Args:
            mapping_date (str): The catalogue's mapping date as "YYYY-MM-DD".

        Returns:
            Path: The index file's path, whether or not it exists.
        """
        return (
            self.index_directory / f'{_FILE_PREFIX}{mapping_date}{_FILE_SUFFIX}'
        )

    def existing_files(self) -> list[tuple[str, Path]]:
        """Lists the complete index files, newest mapping date first.

        Returns:
            list[tuple[str, Path]]: A list of tuples (mapping date, path).
        """
        found = []
        if not self.index_directory.is_dir():
            return found
        for path in self.index_directory.glob(f'{_FILE_PREFIX}*{_FILE_SUFFIX}'):
            mapping_date = path.name[len(_FILE_PREFIX) : -len(_FILE_SUFFIX)]
            found.append((mapping_date, path))
        found.sort(reverse=True)
        return found

    async def build(
        self,
        company_names: dict[str, str] | None = None,
    ) -> tuple[Path, str]:
        """Downloads the catalogue and writes its index file.

        Args:
            company_names (dict[str, str] | None): Company names by trading symbol, given to shares and to the derivatives on them so they can be found by name, or None for none.

        Returns:
            tuple[Path, str]: A tuple (path of the new index file, mapping date).

        Raises:
            UnifiedBrokerInterfaceError: The catalogue could not be downloaded.
            ValueError: The catalogue arrived incomplete.
            sqlite3.Error: The index file could not be written.
        """
        self.index_directory.mkdir(parents=True, exist_ok=True)
        today = self._today()
        temporary_path = (
            self.index_directory / f'building-{today}{_FILE_SUFFIX}'
        )
        temporary_path.unlink(missing_ok=True)
        self.stored_count = 0
        self._seen_ids = set()
        self._company_names = company_names or {}
        connection = await asyncio.to_thread(
            self._create_database,
            temporary_path,
        )
        try:

            async def store_batch(batch: list[dict[str, Any]]) -> None:
                """Stores one downloaded batch in the database.

                Args:
                    batch (list[dict[str, Any]]): Identity documents from UBI.
                """
                await asyncio.to_thread(
                    self._store_batch,
                    connection,
                    batch,
                    today,
                )

            mapping_date = await self._client.download_master(store_batch)
            await asyncio.to_thread(
                self._finish_database,
                connection,
                mapping_date,
                today,
            )
        except BaseException:
            connection.close()
            temporary_path.unlink(missing_ok=True)
            raise
        finally:
            self._seen_ids = set()
        connection.close()
        final_path = self.path_for(mapping_date)
        temporary_path.replace(final_path)
        _LOGGER.info(
            'Built the instrument index for mapping date %s with %d instruments.',
            mapping_date,
            self.stored_count,
        )
        return final_path, mapping_date

    def _today(self) -> str:
        """Finds today's local date.

        Returns:
            str: Today as "YYYY-MM-DD".
        """
        moment = datetime.datetime.fromtimestamp(self._time_source.now())  # noqa: DTZ006
        return moment.date().isoformat()

    def _create_database(self, path: Path) -> sqlite3.Connection:
        """Creates the empty index database.

        Args:
            path (Path): The file to create.

        Returns:
            sqlite3.Connection: The open connection.

        Raises:
            sqlite3.Error: The database could not be created.
        """
        connection = sqlite3.connect(path, check_same_thread=False)
        connection.execute('PRAGMA journal_mode = OFF')
        connection.execute('PRAGMA synchronous = OFF')
        for statement in _SCHEMA:
            connection.execute(statement)
        return connection

    def _store_batch(
        self,
        connection: sqlite3.Connection,
        batch: list[dict[str, Any]],
        today: str,
    ) -> None:
        """Stores the unexpired instruments of one batch with their search words.

        Args:
            connection (sqlite3.Connection): The index database.
            batch (list[dict[str, Any]]): Identity documents from UBI.
            today (str): Today as "YYYY-MM-DD"; instruments that expired earlier are left out.

        Raises:
            sqlite3.Error: The rows could not be written.
        """
        instrument_rows = []
        search_rows = []
        for record in batch:
            instrument_id = record.get('instrument_id')
            if not instrument_id or instrument_id in self._seen_ids:
                continue
            expiry_date = record.get('expiry_date')
            if expiry_date is not None and expiry_date < today:
                continue
            self._seen_ids.add(instrument_id)
            self.stored_count += 1
            row_number = self.stored_count
            instrument_row = self._instrument_row(row_number, record)
            instrument_rows.append(instrument_row)
            search_text = self._text_builder.build(record)
            company_name = self._company_name(record)
            if company_name:
                search_text = f'{search_text} {company_name.lower()}'
            search_rows.append(
                (
                    row_number,
                    search_text,
                )
            )
        with connection:
            connection.executemany(_INSERT_INSTRUMENT, instrument_rows)
            connection.executemany(_INSERT_SEARCH_TEXT, search_rows)

    def _instrument_row(
        self,
        row_number: int,
        record: dict[str, Any],
    ) -> tuple[Any, ...]:
        """Works out the stored columns of one instrument.

        Args:
            row_number (int): The row's number, which is also its full-text row id.
            record (dict[str, Any]): The instrument's identity document.

        Returns:
            tuple[Any, ...]: The values for the INSERT statement, in column order.
        """
        exchange = record['exchange']
        segment = record['segment']
        shape = record['shape']
        bare_segment = self._classifier.bare_segment(exchange, segment)
        root_name = (
            record.get('underlying_symbol') or record.get('symbol') or ''
        )
        expiry_date = record.get('expiry_date')
        expiry_month = None
        if expiry_date is not None:
            expiry_month = expiry_date[:7]
        return (
            row_number,
            record['instrument_id'],
            exchange,
            segment,
            bare_segment,
            self._classifier.asset_class(bare_segment),
            shape,
            1 if self._classifier.is_index(bare_segment) else 0,
            record.get('symbol'),
            record.get('underlying_symbol'),
            root_name,
            root_name.lower().replace(' ', ''),
            self._namer.name(
                shape,
                record.get('symbol'),
                record.get('underlying_symbol'),
                expiry_date,
                record.get('strike_price'),
                record.get('option_type'),
            ),
            self._company_name(record),
            expiry_date,
            expiry_month,
            record.get('strike_price'),
            record.get('option_type'),
            self._classifier.exchange_rank(exchange),
            self._classifier.shape_rank(shape),
        )

    def _company_name(self, record: dict[str, Any]) -> str | None:
        """Finds the company name of a share or of a derivative on a share.

        Args:
            record (dict[str, Any]): The instrument's identity document.

        Returns:
            str | None: The company's name, or None for anything that is not a company's share or a derivative on one.
        """
        bare_segment = self._classifier.bare_segment(
            record['exchange'],
            record['segment'],
        )
        if self._classifier.is_index(bare_segment):
            return None
        if self._classifier.asset_class(bare_segment) not in (
            'equity',
            'other',
        ):
            return None
        root_name = (
            record.get('underlying_symbol') or record.get('symbol') or ''
        )
        return self._company_names.get(root_name)

    def _finish_database(
        self,
        connection: sqlite3.Connection,
        mapping_date: str,
        today: str,
    ) -> None:
        """Adds the lookup indexes and the index's own details.

        Args:
            connection (sqlite3.Connection): The index database.
            mapping_date (str): The catalogue's mapping date.
            today (str): Today as "YYYY-MM-DD".

        Raises:
            sqlite3.Error: The database could not be written.
        """
        with connection:
            for statement in _FINISHING_STATEMENTS:
                connection.execute(statement)
            connection.executemany(
                'INSERT INTO index_details (name, value) VALUES (?, ?)',
                [
                    (
                        'mapping_date',
                        mapping_date,
                    ),
                    (
                        'built_on',
                        today,
                    ),
                    (
                        'instrument_count',
                        str(self.stored_count),
                    ),
                    (
                        'schema_version',
                        SCHEMA_VERSION,
                    ),
                ],
            )
        connection.execute('ANALYZE')
