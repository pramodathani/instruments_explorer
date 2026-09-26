"""Runs knowledge fetch jobs one at a time in the background and reports their progress.

A job runs the chosen fetchers for one company in turn. Each fetcher is a step with its own status and message, so one site failing never stops the others. Every change is saved to MongoDB and announced to open browsers.

Typical usage example:

  runner = FetchJobRunner(fetchers, service, jobs, announce, clock)
  task = asyncio.create_task(runner.run())
  job = await runner.submit(company, ['screener', 'yahoo'], 'requested')
"""

import asyncio
import logging
import uuid
from collections.abc import Callable, Sequence
from typing import Any

from instruments_explorer.knowledge import company_identity
from instruments_explorer.knowledge import knowledge_service
from instruments_explorer.knowledge.fetchers import base
from instruments_explorer.storage import fetch_job_repository
from instruments_explorer.utilities import clock

_LOGGER = logging.getLogger(__name__)
FETCHER_TIMEOUT_SECONDS = 120.0


class FetchJobRunner:
    """Queues fetch jobs and runs them in order.

    Attributes:
        fetchers: Every fetcher by key, in the order a job runs them.
    """

    def __init__(
        self,
        fetchers: Sequence[base.BaseFetcher],
        service: knowledge_service.KnowledgeService,
        jobs: fetch_job_repository.FetchJobRepository,
        announce: Callable[[dict[str, Any]], None],
        time_source: clock.SystemClock,
    ):
        """Creates the runner.

        Args:
            fetchers (Sequence[base.BaseFetcher]): Every fetcher, in the order jobs run them.
            service (knowledge_service.KnowledgeService): Stores what the fetchers find.
            jobs (fetch_job_repository.FetchJobRepository): Stores the jobs.
            announce (Callable[[dict[str, Any]], None]): Called with a message for open browsers after every change to a job.
            time_source (clock.SystemClock): The source of the current time.
        """
        self.fetchers = {}
        for fetcher in fetchers:
            self.fetchers[fetcher.key] = fetcher
        self._service = service
        self._jobs = jobs
        self._announce = announce
        self._time_source = time_source
        self._queue = asyncio.Queue()
        self._active = {}

    def describe_fetchers(self) -> list[dict[str, Any]]:
        """Describes every fetcher for the browser.

        Returns:
            list[dict[str, Any]]: One description per fetcher.
        """
        descriptions = []
        for fetcher in self.fetchers.values():
            descriptions.append(fetcher.describe())
        return descriptions

    def news_sources(self) -> list[str]:
        """Lists the fetchers that collect news.

        Returns:
            list[str]: Their keys.
        """
        keys = []
        for fetcher in self.fetchers.values():
            if fetcher.news:
                keys.append(fetcher.key)
        return keys

    async def submit(
        self,
        company: company_identity.CompanyIdentity,
        sources: Sequence[str] | None,
        reason: str,
    ) -> dict[str, Any]:
        """Queues a job for a company, or returns the job already queued or running for it.

        Args:
            company (company_identity.CompanyIdentity): The company.
            sources (Sequence[str] | None): The fetcher keys to run, or None for every available fetcher.
            reason (str): Why the job was started, such as "requested" or "scheduled news refresh".

        Returns:
            dict[str, Any]: The job.

        Raises:
            ValueError: A source key is unknown.
        """
        existing = self._active.get(company.company_key)
        if existing is not None:
            return existing
        chosen = []
        for key in sources if sources is not None else list(self.fetchers):
            fetcher = self.fetchers.get(key)
            if fetcher is None:
                raise ValueError(f'Unknown knowledge source: {key!r}')
            available, _ = fetcher.available()
            if available or sources is not None:
                chosen.append(fetcher)
        steps = []
        for fetcher in chosen:
            available, reason_unavailable = fetcher.available()
            steps.append(
                {
                    'source': fetcher.key,
                    'label': fetcher.label,
                    'status': 'queued' if available else 'skipped',
                    'message': '' if available else reason_unavailable,
                    'documents': 0,
                    'new': 0,
                }
            )
        job = {
            'job_id': uuid.uuid4().hex,
            'company': company.describe(),
            'reason': reason,
            'status': 'queued',
            'steps': steps,
            'created_at': self._time_source.now(),
            'finished_at': None,
        }
        self._active[company.company_key] = job
        await self._save(job)
        await self._queue.put(
            (
                company,
                job,
            )
        )
        return job

    async def run(self) -> None:
        """Runs queued jobs one after another until cancelled."""
        while True:
            company, job = await self._queue.get()
            try:
                await self._run_job(company, job)
            finally:
                self._active.pop(company.company_key, None)
                self._queue.task_done()

    async def _run_job(
        self,
        company: company_identity.CompanyIdentity,
        job: dict[str, Any],
    ) -> None:
        """Runs one job's steps in order.

        Args:
            company (company_identity.CompanyIdentity): The company.
            job (dict[str, Any]): The job, changed in place as it runs.
        """
        job['status'] = 'running'
        await self._save(job)
        succeeded = 0
        attempted = 0
        for step in job['steps']:
            if step['status'] == 'skipped':
                continue
            attempted += 1
            step['status'] = 'running'
            await self._save(job)
            fetcher = self.fetchers[step['source']]
            try:
                result = await asyncio.wait_for(
                    fetcher.fetch(company),
                    FETCHER_TIMEOUT_SECONDS,
                )
                stored = await self._service.store(company, fetcher.key, result)
            except Exception as error:  # noqa: BLE001
                step['status'] = 'failed'
                step['message'] = f'{type(error).__name__}: {error}'[:300]
                _LOGGER.warning(
                    'Knowledge source %s failed for %s: %s',
                    fetcher.key,
                    company.symbol,
                    error,
                )
            else:
                succeeded += 1
                step['status'] = 'done'
                step['message'] = result.message
                step['documents'] = stored['documents']
                step['new'] = stored['new']
            await self._save(job)
        job['status'] = 'done' if succeeded or attempted == 0 else 'failed'
        job['finished_at'] = self._time_source.now()
        await self._save(job)

    async def _save(self, job: dict[str, Any]) -> None:
        """Saves a job and tells open browsers about it.

        Args:
            job (dict[str, Any]): The job.
        """
        await self._jobs.save(job)
        self._announce(
            {
                'type': 'fetch_job',
                'job': job,
            }
        )
