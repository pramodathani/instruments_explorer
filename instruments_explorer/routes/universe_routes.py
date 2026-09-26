"""The route that serves the 3D universe map.

Typical usage example:

  web_application.include_router(UniverseRoutes(service, guard).router)
"""

from typing import Any

import fastapi

from instruments_explorer.security import session_guard
from instruments_explorer.universe import universe_service


class UniverseRoutes:
    """The /api/universe route.

    Attributes:
        service: Builds the universe map.
        router: The FastAPI router holding the route.
    """

    def __init__(
        self,
        service: universe_service.UniverseService,
        guard: session_guard.SessionGuard,
    ):
        """Creates the route.

        Args:
            service (universe_service.UniverseService): Builds the universe map.
            guard (session_guard.SessionGuard): Requires a logged-in session.
        """
        self.service = service
        self.router = fastapi.APIRouter(
            dependencies=[
                fastapi.Depends(guard.require_session),
            ],
        )
        self.router.add_api_route(
            '/api/universe',
            self.universe,
            methods=[
                'GET',
            ],
        )

    async def universe(self, include_options: bool = False) -> dict[str, Any]:
        """Serves the laid-out universe.

        Args:
            include_options (bool): Whether to include options.

        Returns:
            dict[str, Any]: The universe from UniverseService.universe.

        Raises:
            fastapi.HTTPException: 503 while the index is not ready.
        """
        try:
            return await self.service.universe(include_options)
        except LookupError as error:
            raise fastapi.HTTPException(
                status_code=503, detail=str(error)
            ) from error
