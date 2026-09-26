"""The routes that refresh screener figures and run screens.

Typical usage example:

  web_application.include_router(ScreenerRoutes(parts, guard).router)
"""

from typing import Annotated, Any

import fastapi
import pydantic

from instruments_explorer.screener import screener_service
from instruments_explorer.screener import screener_universe
from instruments_explorer.screener import snapshot_job
from instruments_explorer.screener.conditions import condition_catalogue
from instruments_explorer.security import session_guard
from instruments_explorer.storage import screener_repository

RepeatedValues = Annotated[list[str] | None, fastapi.Query()]


class RefreshRequest(pydantic.BaseModel):
    """The body of a request to refresh a universe's figures.

    Attributes:
        universe: The universe key.
    """

    universe: str = 'total_market'


class ScreenerParts:
    """The components the screener routes use.

    Attributes:
        universe: Lists the stocks.
        job: Computes the figures.
        service: Runs screens.
        catalogue: Lists the conditions.
        repository: Reads the runs.
    """

    def __init__(
        self,
        universe: screener_universe.ScreenerUniverse,
        job: snapshot_job.ScreenerSnapshotJob,
        service: screener_service.ScreenerService,
        catalogue: condition_catalogue.ConditionCatalogue,
        repository: screener_repository.ScreenerRepository,
    ):
        """Gathers the components.

        Args:
            universe (screener_universe.ScreenerUniverse): Lists the stocks.
            job (snapshot_job.ScreenerSnapshotJob): Computes the figures.
            service (screener_service.ScreenerService): Runs screens.
            catalogue (condition_catalogue.ConditionCatalogue): Lists the conditions.
            repository (screener_repository.ScreenerRepository): Reads the runs.
        """
        self.universe = universe
        self.job = job
        self.service = service
        self.catalogue = catalogue
        self.repository = repository


class ScreenerRoutes:
    """The /api/screener routes.

    Attributes:
        parts: The components the routes use.
        router: The FastAPI router holding the routes.
    """

    def __init__(self, parts: ScreenerParts, guard: session_guard.SessionGuard):
        """Creates the routes.

        Args:
            parts (ScreenerParts): The components the routes use.
            guard (session_guard.SessionGuard): Requires a logged-in session, and the application header on the POST route.
        """
        self.parts = parts
        self.router = fastapi.APIRouter(
            dependencies=[
                fastapi.Depends(guard.require_session),
            ],
        )
        self.router.add_api_route(
            '/api/screener/setup',
            self.setup,
            methods=[
                'GET',
            ],
        )
        self.router.add_api_route(
            '/api/screener/run',
            self.run,
            methods=[
                'GET',
            ],
        )
        self.router.add_api_route(
            '/api/screener/refresh',
            self.refresh,
            methods=[
                'POST',
            ],
            dependencies=[
                fastapi.Depends(guard.require_app_header),
            ],
        )

    async def setup(self) -> dict[str, Any]:
        """Describes the universes, conditions, sortable figures, the current run and each universe's last finished run.

        Returns:
            dict[str, Any]: "universes", "conditions", "sortable", "job" and "last_runs".
        """
        last_runs = {}
        for universe in screener_universe.UNIVERSES:
            last_runs[universe] = await self.parts.repository.latest_run(
                universe,
                finished_only=True,
            )
        return {
            'universes': self.parts.universe.describe(),
            'conditions': self.parts.catalogue.describe(),
            'sortable': screener_service.SORTABLE_FIGURES,
            'job': self.parts.job.state,
            'last_runs': last_runs,
        }

    async def refresh(self, body: RefreshRequest) -> dict[str, Any]:
        """Starts computing a universe's figures, or returns the run in progress.

        Args:
            body (RefreshRequest): Which universe.

        Returns:
            dict[str, Any]: The run's state.

        Raises:
            fastapi.HTTPException: 400 for an unknown universe, 503 while the index is not ready.
        """
        try:
            return await self.parts.job.start(body.universe)
        except ValueError as error:
            raise fastapi.HTTPException(
                status_code=400, detail=str(error)
            ) from error
        except LookupError as error:
            raise fastapi.HTTPException(
                status_code=503, detail=str(error)
            ) from error

    async def run(
        self,
        universe: str = 'total_market',
        condition: RepeatedValues = None,
        sector: RepeatedValues = None,
        sort: str = 'change_1d',
        descending: bool = True,
        limit: int = 300,
    ) -> dict[str, Any]:
        """Runs a screen over a universe's stored figures.

        Args:
            universe (str): The universe key.
            condition (RepeatedValues): Condition requests such as "rsi:0:30", given once per condition.
            sector (RepeatedValues): Sectors to keep, given once per sector.
            sort (str): The figure to sort by.
            descending (bool): Whether to sort largest first.
            limit (int): The largest number of rows.

        Returns:
            dict[str, Any]: The screen's answer from ScreenerService.run.

        Raises:
            fastapi.HTTPException: 400 for an invalid condition, sort, limit or universe, 503 while the index is not ready.
        """
        try:
            return await self.parts.service.run(
                universe,
                list(condition or []),
                list(sector or []),
                sort,
                descending,
                limit,
            )
        except ValueError as error:
            raise fastapi.HTTPException(
                status_code=400, detail=str(error)
            ) from error
        except LookupError as error:
            raise fastapi.HTTPException(
                status_code=503, detail=str(error)
            ) from error
