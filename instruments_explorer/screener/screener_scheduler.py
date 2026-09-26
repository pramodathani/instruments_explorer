"""Refreshes the default universe's screener figures once a day, after UBI loads the day's prices.

UBI loads daily candles at 08:30 India time, so a run is due when the last finished run is older than twenty hours and it is past 09:00 India time.

Typical usage example:

  task = asyncio.create_task(ScreenerScheduler(job, repository, clock).run())
"""

import asyncio
import datetime
import logging

from instruments_explorer.screener import snapshot_job
from instruments_explorer.storage import screener_repository
from instruments_explorer.utilities import clock

_LOGGER = logging.getLogger(__name__)
DEFAULT_UNIVERSE = 'total_market'
CHECK_SECONDS = 30 * 60
STALE_SECONDS = 20 * 60 * 60
START_HOUR = 9
_INDIA = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


class ScreenerScheduler:
    """Starts a snapshot run of the default universe whenever one is due."""

    def __init__(
        self,
        job: snapshot_job.ScreenerSnapshotJob,
        repository: screener_repository.ScreenerRepository,
        time_source: clock.SystemClock,
        first_check_seconds: float = 120.0,
    ):
        """Creates the scheduler.

        Args:
            job (snapshot_job.ScreenerSnapshotJob): Runs the snapshots.
            repository (screener_repository.ScreenerRepository): Knows when the last run finished.
            time_source (clock.SystemClock): The source of the current time.
            first_check_seconds (float): How long after start-up the first check waits, so start-up is not slowed.
        """
        self._job = job
        self._repository = repository
        self._time_source = time_source
        self._first_check_seconds = first_check_seconds

    async def run(self) -> None:
        """Checks after a short wait and then every CHECK_SECONDS, until cancelled."""
        await asyncio.sleep(self._first_check_seconds)
        while True:
            try:
                if await self.due():
                    await self._job.start(DEFAULT_UNIVERSE)
                    _LOGGER.info('Started the daily screener snapshot.')
            except Exception as error:  # noqa: BLE001
                _LOGGER.warning('The screener schedule check failed: %s', error)
            await asyncio.sleep(CHECK_SECONDS)

    async def due(self) -> bool:
        """Says whether a run of the default universe should start now.

        Returns:
            bool: True when no run is in progress, it is past START_HOUR in India, and the last finished run is missing or older than STALE_SECONDS.
        """
        if self._job.running():
            return False
        now = self._time_source.now()
        hour = datetime.datetime.fromtimestamp(now, tz=_INDIA).hour
        if hour < START_HOUR:
            return False
        last = await self._repository.latest_run(
            DEFAULT_UNIVERSE, finished_only=True
        )
        if last is None:
            return True
        return now - last['started_at'] > STALE_SECONDS
