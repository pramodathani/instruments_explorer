"""Keeps the instrument index in step with UBI's catalogue.

UBI maps its catalogue once each morning. The maintainer checks UBI's mapping date every ten minutes and builds a new index when the date changes, while searches keep using the previous index until the new one is ready.

Typical usage example:

  maintainer = InstrumentIndexMaintainer(client, builder, clock)
  maintainer.open_newest_existing()
  task = asyncio.create_task(maintainer.run())
"""

import asyncio
import datetime
import logging
import sqlite3
from typing import Any

from instruments_explorer.instruments import instrument_index
from instruments_explorer.instruments import instrument_index_builder
from instruments_explorer.unified_broker_interface import exceptions
from instruments_explorer.unified_broker_interface import rest_client
from instruments_explorer.utilities import clock

_LOGGER = logging.getLogger(__name__)
_FILES_KEPT = 2


class InstrumentIndexMaintainer:
    """Opens, rebuilds and swaps the instrument index.

    Attributes:
        check_interval_seconds: How long to wait between checks of UBI's mapping date, in seconds.
        current_index: The index searches use, or None before the first index is ready.
        state: "starting", "building", "ready" or "unavailable".
        last_error: The last failure, or None.
    """

    def __init__(
        self,
        client: rest_client.UnifiedBrokerInterfaceClient,
        builder: instrument_index_builder.InstrumentIndexBuilder,
        time_source: clock.SystemClock,
        check_interval_seconds: float = 600.0,
    ):
        """Creates the maintainer without opening anything.

        Args:
            client (rest_client.UnifiedBrokerInterfaceClient): Reads UBI's mapping date.
            builder (instrument_index_builder.InstrumentIndexBuilder): Builds index files.
            time_source (clock.SystemClock): The source of today's date.
            check_interval_seconds (float): How long to wait between checks, in seconds.
        """
        self.check_interval_seconds = check_interval_seconds
        self.current_index = None
        self.state = 'starting'
        self.last_error = None
        self._client = client
        self._builder = builder
        self._time_source = time_source
        self._lock = asyncio.Lock()

    def today(self) -> str:
        """Finds today's local date.

        Returns:
            str: Today as "YYYY-MM-DD".
        """
        moment = datetime.datetime.fromtimestamp(self._time_source.now())  # noqa: DTZ006
        return moment.date().isoformat()

    def open_newest_existing(self) -> None:
        """Opens the newest complete index file left by an earlier run, so search works before UBI is reached."""
        for mapping_date, path in self._builder.existing_files():
            try:
                self._swap(instrument_index.InstrumentIndex.open(path))
            except sqlite3.Error as error:
                _LOGGER.warning(
                    'Skipping unreadable instrument index %s: %s',
                    path,
                    error,
                )
                continue
            _LOGGER.info(
                'Opened the instrument index for mapping date %s.',
                mapping_date,
            )
            return

    async def run(self) -> None:
        """Checks UBI's mapping date now and then every check interval, until cancelled."""
        while True:
            await self.refresh()
            await asyncio.sleep(self.check_interval_seconds)

    async def refresh(self) -> None:
        """Builds and opens a new index when UBI's mapping date has changed.

        Failures are recorded in last_error and logged, and the previous index stays in use.
        """
        async with self._lock:
            try:
                await self._refresh()
            except (
                exceptions.UnifiedBrokerInterfaceError,
                ValueError,
                OSError,
                sqlite3.Error,
            ) as error:
                self.last_error = str(error)
                if self.current_index is None:
                    self.state = 'unavailable'
                else:
                    self.state = 'ready'
                _LOGGER.warning('Instrument index refresh failed: %s', error)

    def status(self) -> dict[str, Any]:
        """Describes the index for the browser.

        Returns:
            dict[str, Any]: "state", "mapping_date", "instrument_count", "building_count" (instruments stored so far while building, otherwise None) and "last_error".
        """
        mapping_date = None
        instrument_count = 0
        if self.current_index is not None:
            mapping_date = self.current_index.mapping_date
            instrument_count = self.current_index.instrument_count
        building_count = None
        if self.state == 'building':
            building_count = self._builder.stored_count
        return {
            'state': self.state,
            'mapping_date': mapping_date,
            'instrument_count': instrument_count,
            'building_count': building_count,
            'last_error': self.last_error,
        }

    async def _refresh(self) -> None:
        """Does the work of refresh.

        Raises:
            UnifiedBrokerInterfaceError: UBI could not be read.
            ValueError: The catalogue arrived incomplete.
            OSError: The index file could not be written.
            sqlite3.Error: The index file could not be written or opened.
        """
        segments = await self._client.instrument_segments()
        mapping_date = segments.get('mapping_date')
        current = self.current_index
        if current is not None and current.mapping_date == mapping_date:
            self.state = 'ready'
            self.last_error = None
            return
        path = self._builder.path_for(str(mapping_date))
        if not path.is_file():
            self.state = 'building'
            path, _ = await self._builder.build()
        new_index = await asyncio.to_thread(
            instrument_index.InstrumentIndex.open,
            path,
        )
        self._swap(new_index)
        self.last_error = None
        await asyncio.to_thread(self._remove_old_files)

    def _swap(self, new_index: instrument_index.InstrumentIndex) -> None:
        """Makes a new index current and closes the previous one.

        Args:
            new_index (instrument_index.InstrumentIndex): The index to use from now on.
        """
        previous = self.current_index
        self.current_index = new_index
        self.state = 'ready'
        if previous is not None and previous.path != new_index.path:
            previous.close()

    def _remove_old_files(self) -> None:
        """Deletes all but the newest index files."""
        existing = self._builder.existing_files()
        for _, path in existing[_FILES_KEPT:]:
            if (
                self.current_index is not None
                and path == self.current_index.path
            ):
                continue
            path.unlink(missing_ok=True)
