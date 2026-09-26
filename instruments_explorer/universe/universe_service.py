"""Serves the universe map: the layout from the index, coloured by each instrument's latest change.

Laying out tens of thousands of instruments and reading their quotes takes a moment, so both are cached: the layout until the index changes, and the changes for a minute.

Typical usage example:

  service = UniverseService(maintainer, snapshot_reader, clock)
  answer = await service.universe(include_options=False)
"""

import asyncio
from typing import Any

from instruments_explorer.instruments import instrument_index_maintainer
from instruments_explorer.market import quote_snapshot_reader
from instruments_explorer.universe import universe_layout
from instruments_explorer.utilities import clock

CHANGES_SECONDS = 60.0


class UniverseService:
    """Builds and caches the universe map."""

    def __init__(
        self,
        maintainer: instrument_index_maintainer.InstrumentIndexMaintainer,
        snapshot_reader: quote_snapshot_reader.QuoteSnapshotReader,
        time_source: clock.SystemClock,
    ):
        """Creates the service.

        Args:
            maintainer (instrument_index_maintainer.InstrumentIndexMaintainer): Holds the instrument index.
            snapshot_reader (quote_snapshot_reader.QuoteSnapshotReader): Reads many live quotes at once.
            time_source (clock.SystemClock): The source of the current time.
        """
        self._maintainer = maintainer
        self._snapshot_reader = snapshot_reader
        self._time_source = time_source
        self._layout = universe_layout.UniverseLayout()
        self._layouts = {}
        self._changes = {}
        self._lock = asyncio.Lock()

    async def universe(self, include_options: bool) -> dict[str, Any]:
        """Gives the laid-out universe with each instrument's latest change.

        Args:
            include_options (bool): Whether to include options.

        Returns:
            dict[str, Any]: The layout from UniverseLayout.build, plus "changes" (percent per point, None where no quote is held), "quoted" (how many points have a change), "mapping_date" and "include_options".

        Raises:
            LookupError: The instrument index is not ready.
        """
        index = self._maintainer.current_index
        if index is None:
            raise LookupError('The instrument index is not ready yet.')
        async with self._lock:
            key = (
                index.path,
                include_options,
            )
            layout = self._layouts.get(key)
            if layout is None:
                records = await asyncio.to_thread(
                    index.universe_records, include_options
                )
                layout = await asyncio.to_thread(self._layout.build, records)
                self._layouts = {
                    key: layout,
                }
            cached = self._changes.get(key)
            now = self._time_source.now()
            if cached is None or now - cached[0] > CHANGES_SECONDS:
                quotes = await self._snapshot_reader.read(layout['ids'])
                changes = []
                for instrument_id in layout['ids']:
                    quote = quotes.get(instrument_id)
                    value = quote.get('change_percent') if quote else None
                    changes.append(
                        round(value, 2)
                        if isinstance(value, (int, float))
                        else None
                    )
                cached = (
                    now,
                    changes,
                )
                self._changes[key] = cached
        answer = dict(layout)
        answer['changes'] = cached[1]
        answer['quoted'] = sum(1 for value in cached[1] if value is not None)
        answer['mapping_date'] = index.mapping_date
        answer['include_options'] = include_options
        return answer
