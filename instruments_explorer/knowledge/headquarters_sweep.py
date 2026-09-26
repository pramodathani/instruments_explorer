"""Fetches Yahoo's profile, which includes the headquarters address and officers, for every Nifty Total Market company not yet located, so the Earth page can place them all.

The sweep runs in the background one company at a time, waiting between companies so Yahoo is not hammered, and skips companies that already have a headquarters. Progress is announced to browsers as "locate_job" events carrying the state under "job".

Typical usage example:

  sweep = HeadquartersSweep(yahoo_fetcher, service, companies, hub.broadcast_event, clock, 2.0)
  state = await sweep.start()
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from instruments_explorer.knowledge import company_identity
from instruments_explorer.knowledge import knowledge_service
from instruments_explorer.knowledge.fetchers import base
from instruments_explorer.storage import company_repository
from instruments_explorer.utilities import clock

_LOGGER = logging.getLogger(__name__)


class HeadquartersSweep:
    """Locates every index company in the background.

    Attributes:
        state: The current or last run: "status", "total", "done", "located", "skipped", "failed", "started_at" and "finished_at", or None before the first run.
    """

    def __init__(
        self,
        fetcher: base.BaseFetcher,
        service: knowledge_service.KnowledgeService,
        companies: company_repository.CompanyRepository,
        announce: Callable[[dict[str, Any]], None],
        time_source: clock.SystemClock,
        interval_seconds: float,
    ):
        """Keeps the components.

        Args:
            fetcher (base.BaseFetcher): The Yahoo fetcher.
            service (knowledge_service.KnowledgeService): Stores what the fetcher finds.
            companies (company_repository.CompanyRepository): Lists the index companies.
            announce (Callable[[dict[str, Any]], None]): Sends progress to browsers.
            time_source (clock.SystemClock): The source of the current time.
            interval_seconds (float): How long to wait between companies.
        """
        self._fetcher = fetcher
        self._service = service
        self._companies = companies
        self._announce = announce
        self._time_source = time_source
        self._interval_seconds = interval_seconds
        self._task: asyncio.Task | None = None
        self.state: dict[str, Any] | None = None

    async def start(self) -> dict[str, Any]:
        """Starts a sweep, or returns the one already running.

        Returns:
            dict[str, Any]: The run's state.
        """
        if self.state is not None and self.state['status'] == 'running':
            return self.state
        members = await self._companies.screener_members(True)
        waiting = []
        skipped = 0
        for member in members:
            if member.get('headquarters'):
                skipped += 1
            else:
                waiting.append(member)
        self.state = {
            'status': 'running',
            'total': len(members),
            'done': 0,
            'located': 0,
            'skipped': skipped,
            'failed': 0,
            'started_at': self._time_source.now(),
            'finished_at': None,
        }
        self._task = asyncio.create_task(self._run(waiting, self.state))
        self._publish(self.state)
        return self.state

    async def _run(
        self, waiting: list[dict[str, Any]], state: dict[str, Any]
    ) -> None:
        """Fetches each waiting company in turn.

        Args:
            waiting (list[dict[str, Any]]): The companies without a headquarters.
            state (dict[str, Any]): The run's state, changed in place.
        """
        try:
            for position, member in enumerate(waiting):
                company = company_identity.CompanyIdentity(
                    member['company_key'],
                    member.get('name') or member['symbol'],
                    member.get('isin'),
                    'nse',
                    member['symbol'],
                )
                try:
                    result = await self._fetcher.fetch(company)
                    await self._service.store(
                        company, self._fetcher.key, result
                    )
                    if 'headquarters' in result.profile:
                        state['located'] += 1
                except Exception as error:  # noqa: BLE001
                    state['failed'] += 1
                    _LOGGER.info(
                        'Locating %s failed: %s', member['symbol'], error
                    )
                state['done'] += 1
                if position % 5 == 0:
                    self._publish(state)
                await asyncio.sleep(self._interval_seconds)
            state['status'] = 'done'
        except asyncio.CancelledError:
            state['status'] = 'cancelled'
            raise
        finally:
            state['finished_at'] = self._time_source.now()
            self._publish(state)

    def _publish(self, state: dict[str, Any]) -> None:
        """Tells open browsers about the sweep's progress.

        Args:
            state (dict[str, Any]): The sweep's state.
        """
        self._announce(
            {
                'type': 'locate_job',
                'job': dict(state),
            }
        )
