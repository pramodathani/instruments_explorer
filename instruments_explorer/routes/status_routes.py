"""The route that reports whether the project's own stores and the chat assistant are ready.

Typical usage example:

  web_application.include_router(
      StatusRoutes(explorer_settings, checkers, guard).router
  )
"""

import asyncio
from collections.abc import Sequence
from typing import Any, Protocol

import fastapi

from instruments_explorer.configuration import settings
from instruments_explorer.security import session_guard


class StoreChecker(Protocol):
    """Anything that can report whether one store is reachable."""

    async def check(self) -> dict[str, Any]:
        """Reports whether the store is reachable.

        Returns:
            dict[str, Any]: {"name", "reachable", "detail"}.
        """


class StatusRoutes:
    """The /api/status route.

    Attributes:
        explorer_settings: Supplies the assistant's model and whether it has a key.
        checkers: One checker per store.
        router: The FastAPI router holding the route.
    """

    def __init__(
        self,
        explorer_settings: settings.Settings,
        checkers: Sequence[StoreChecker],
        guard: session_guard.SessionGuard,
    ):
        """Creates the route.

        Args:
            explorer_settings (settings.Settings): Supplies the assistant's model and whether it has a key.
            checkers (Sequence[StoreChecker]): One checker per store.
            guard (session_guard.SessionGuard): Requires a logged-in session.
        """
        self.explorer_settings = explorer_settings
        self.checkers = checkers
        self.router = fastapi.APIRouter()
        self.router.add_api_route(
            '/api/status',
            self.status,
            methods=[
                'GET',
            ],
            dependencies=[
                fastapi.Depends(guard.require_session),
            ],
        )

    async def status(self) -> dict[str, Any]:
        """Checks every store at the same time and describes the assistant.

        Returns:
            dict[str, Any]: {"stores": [...], "assistant": {"configured", "model"}}.
        """
        checks = []
        for checker in self.checkers:
            checks.append(checker.check())
        stores = await asyncio.gather(*checks)
        return {
            'stores': list(stores),
            'assistant': {
                'configured': self.explorer_settings.assistant_configured(),
                'model': self.explorer_settings.claude_model,
            },
        }
