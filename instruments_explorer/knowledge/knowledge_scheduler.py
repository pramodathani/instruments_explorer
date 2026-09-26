"""Fetches news again, every few hours, for companies whose knowledge was fetched before.

Typical usage example:

  scheduler = KnowledgeScheduler(runner, companies, 6.0)
  task = asyncio.create_task(scheduler.run())
"""

import asyncio
import logging

from instruments_explorer.knowledge import company_identity
from instruments_explorer.knowledge import fetch_job_runner
from instruments_explorer.storage import company_repository

_LOGGER = logging.getLogger(__name__)


class KnowledgeScheduler:
    """Queues a news-only job for every fetched company at a fixed interval.

    Attributes:
        interval_hours: How long to wait between refreshes, in hours.
    """

    def __init__(
        self,
        runner: fetch_job_runner.FetchJobRunner,
        companies: company_repository.CompanyRepository,
        interval_hours: float,
    ):
        """Creates the scheduler.

        Args:
            runner (fetch_job_runner.FetchJobRunner): Queues and runs the jobs.
            companies (company_repository.CompanyRepository): Knows which companies were fetched.
            interval_hours (float): How long to wait between refreshes, in hours.
        """
        self.interval_hours = interval_hours
        self._runner = runner
        self._companies = companies

    async def run(self) -> None:
        """Waits one interval, refreshes, and repeats until cancelled; the first refresh is not at start-up, so restarts never cause a burst of requests."""
        while True:
            await asyncio.sleep(self.interval_hours * 60 * 60)
            try:
                count = await self.refresh()
            except Exception as error:  # noqa: BLE001
                _LOGGER.warning('The scheduled news refresh failed: %s', error)
            else:
                _LOGGER.info('Queued news refreshes for %d companies.', count)

    async def refresh(self) -> int:
        """Queues a news-only job for every company fetched before.

        Returns:
            int: The number of jobs queued.
        """
        sources = self._runner.news_sources()
        count = 0
        for company_key in await self._companies.fetched_keys():
            document = await self._companies.find(company_key)
            if document is None or not document.get('symbol'):
                continue
            company = company_identity.CompanyIdentity(
                company_key,
                document.get('name') or document['symbol'],
                document.get('isin'),
                document.get('exchange') or 'nse',
                document['symbol'],
            )
            await self._runner.submit(
                company, sources, 'scheduled news refresh'
            )
            count += 1
        return count
