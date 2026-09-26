"""Computes every stock's screener figures in the background and reports progress.

Each stock's daily candles are read from UBI's prices route, a few stocks at a time, and its figures are stored in MongoDB. Screens then read those stored figures, so running a screen never touches UBI.

Typical usage example:

  job = ScreenerSnapshotJob(universe, client, repository, announce, clock)
  state = await job.start('total_market')
"""

import asyncio
import logging
import uuid
from collections.abc import Callable
from typing import Any

from instruments_explorer.market import candle_series
from instruments_explorer.screener import screener_universe
from instruments_explorer.screener import stock_metrics
from instruments_explorer.storage import screener_repository
from instruments_explorer.unified_broker_interface import exceptions
from instruments_explorer.unified_broker_interface import rest_client
from instruments_explorer.utilities import clock

_LOGGER = logging.getLogger(__name__)
HISTORY_DAYS = 400
CONCURRENCY = 4
ANNOUNCE_EVERY = 20


class ScreenerSnapshotJob:
    """Runs at most one snapshot run at a time.

    Attributes:
        state: The current or last run: "run_id", "universe", "status", "total", "done", "failed", "started_at" and "finished_at", or None before the first run.
    """

    def __init__(
        self,
        universe: screener_universe.ScreenerUniverse,
        client: rest_client.UnifiedBrokerInterfaceClient,
        repository: screener_repository.ScreenerRepository,
        announce: Callable[[dict[str, Any]], None],
        time_source: clock.SystemClock,
    ):
        """Creates the job.

        Args:
            universe (screener_universe.ScreenerUniverse): Lists the stocks.
            client (rest_client.UnifiedBrokerInterfaceClient): Reads candles from UBI.
            repository (screener_repository.ScreenerRepository): Stores figures and runs.
            announce (Callable[[dict[str, Any]], None]): Called with a progress message for open browsers.
            time_source (clock.SystemClock): The source of the current time.
        """
        self.state = None
        self._universe = universe
        self._client = client
        self._repository = repository
        self._announce = announce
        self._time_source = time_source
        self._metrics = stock_metrics.StockMetrics()
        self._task = None

    def running(self) -> bool:
        """Says whether a run is in progress.

        Returns:
            bool: True while a run is in progress.
        """
        return self._task is not None and not self._task.done()

    async def start(self, universe: str) -> dict[str, Any]:
        """Starts a run in the background, or returns the run already in progress.

        Args:
            universe (str): The universe key.

        Returns:
            dict[str, Any]: The run's state.

        Raises:
            ValueError: The universe is unknown.
            LookupError: The instrument index is not ready.
        """
        if self.running():
            return self.state
        members = await self._universe.members(universe)
        self.state = {
            'run_id': uuid.uuid4().hex,
            'universe': universe,
            'status': 'running',
            'total': len(members),
            'done': 0,
            'failed': 0,
            'started_at': self._time_source.now(),
            'finished_at': None,
        }
        await self._repository.save_run(self.state)
        self._task = asyncio.create_task(self._run(members, self.state))
        return self.state

    async def _run(
        self, members: list[dict[str, Any]], state: dict[str, Any]
    ) -> None:
        """Computes every member's figures, a few at a time.

        Args:
            members (list[dict[str, Any]]): The stocks.
            state (dict[str, Any]): The run's state, changed in place.
        """
        limiter = asyncio.Semaphore(CONCURRENCY)

        async def one(member: dict[str, Any]) -> None:
            """Computes and stores one stock's figures.

            Args:
                member (dict[str, Any]): The stock.
            """
            async with limiter:
                stored = await self._compute(member)
            if stored:
                state['done'] += 1
            else:
                state['failed'] += 1
            if (state['done'] + state['failed']) % ANNOUNCE_EVERY == 0:
                self._publish(state)

        try:
            await asyncio.gather(*[one(member) for member in members])
            state['status'] = 'done'
        except asyncio.CancelledError:
            state['status'] = 'cancelled'
            raise
        finally:
            state['finished_at'] = self._time_source.now()
            await self._repository.save_run(state)
            self._publish(state)

    async def _compute(self, member: dict[str, Any]) -> bool:
        """Reads one stock's candles and stores its figures.

        Args:
            member (dict[str, Any]): The stock.

        Returns:
            bool: True when figures were stored, False when UBI failed or the history is too short.
        """
        try:
            document = await self._client.prices(
                member['instrument_id'],
                'day',
                HISTORY_DAYS,
                True,
            )
        except exceptions.UnifiedBrokerInterfaceError as error:
            _LOGGER.info(
                'No screener figures for %s: %s', member['symbol'], error
            )
            return False
        series = candle_series.CandleSeries.from_prices_document(document or {})
        figures = await asyncio.to_thread(self._metrics.compute, series)
        if figures is None:
            return False
        row = dict(member)
        row.update(figures)
        row['computed_at'] = self._time_source.now()
        await self._repository.save(row)
        return True

    def _publish(self, state: dict[str, Any]) -> None:
        """Tells open browsers about the run's progress.

        Args:
            state (dict[str, Any]): The run's state.
        """
        self._announce(
            {
                'type': 'screener_job',
                'job': dict(state),
            }
        )
