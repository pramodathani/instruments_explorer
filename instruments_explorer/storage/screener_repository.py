"""The screener's collections: one snapshot of figures per stock, and a record of each snapshot run.

Typical usage example:

  snapshots = ScreenerRepository(connection.database())
  await snapshots.save(row)
  rows = await snapshots.for_instruments(ids)
"""

from collections.abc import Iterable, Mapping
from typing import Any

_SNAPSHOTS = 'screener_snapshots'
_RUNS = 'screener_runs'


class ScreenerRepository:
    """Reads and writes screener snapshots and runs in the project's own MongoDB."""

    def __init__(self, database: Any):
        """Wraps the project's database.

        Args:
            database (Any): A pymongo AsyncDatabase, or a stand-in with the same collection methods.
        """
        self._snapshots = database[_SNAPSHOTS]
        self._runs = database[_RUNS]

    async def save(self, row: Mapping[str, Any]) -> None:
        """Stores a stock's latest figures, replacing the previous ones.

        Args:
            row (Mapping[str, Any]): The row, with "instrument_id".
        """
        stored = dict(row)
        stored['_id'] = row['instrument_id']
        await self._snapshots.replace_one(
            {
                '_id': row['instrument_id'],
            },
            stored,
            upsert=True,
        )

    async def for_instruments(
        self, instrument_ids: Iterable[str]
    ) -> list[dict[str, Any]]:
        """Reads the latest figures of the given stocks.

        Args:
            instrument_ids (Iterable[str]): The stocks' instrument ids.

        Returns:
            list[dict[str, Any]]: One row per stock that has figures, without _id.
        """
        wanted = set(instrument_ids)
        rows = []
        async for document in self._snapshots.find({}):
            if document['_id'] in wanted:
                cleaned = dict(document)
                cleaned.pop('_id', None)
                rows.append(cleaned)
        return rows

    async def save_run(self, run: Mapping[str, Any]) -> None:
        """Stores a snapshot run's state.

        Args:
            run (Mapping[str, Any]): The run, with "run_id".
        """
        stored = dict(run)
        stored['_id'] = run['run_id']
        await self._runs.replace_one(
            {
                '_id': run['run_id'],
            },
            stored,
            upsert=True,
        )

    async def latest_run(
        self, universe: str, finished_only: bool
    ) -> dict[str, Any] | None:
        """Reads a universe's most recent run.

        Args:
            universe (str): The universe key.
            finished_only (bool): Whether to skip runs that have not finished.

        Returns:
            dict[str, Any] | None: The run without _id, or None when there has been none.
        """
        query = {
            'universe': universe,
        }
        if finished_only:
            query['status'] = 'done'
        cursor = self._runs.find(query).sort('started_at', -1).limit(1)
        async for document in cursor:
            cleaned = dict(document)
            cleaned.pop('_id', None)
            return cleaned
        return None
