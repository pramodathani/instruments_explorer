"""The routes that list underlyings and serve their expiries, option chains and volatility surfaces.

Typical usage example:

  web_application.include_router(DerivativeRoutes(builder, guard).router)
"""

from typing import Any

import fastapi

from instruments_explorer.derivatives import option_chain_builder
from instruments_explorer.security import session_guard

MAXIMUM_UNDERLYINGS = 100


class DerivativeRoutes:
    """The /api/derivatives routes.

    Attributes:
        builder: Builds expiries, chains and surfaces.
        router: The FastAPI router holding the routes.
    """

    def __init__(
        self,
        builder: option_chain_builder.OptionChainBuilder,
        guard: session_guard.SessionGuard,
    ):
        """Creates the routes.

        Args:
            builder (option_chain_builder.OptionChainBuilder): Builds expiries, chains and surfaces.
            guard (session_guard.SessionGuard): Requires a logged-in session.
        """
        self.builder = builder
        self.router = fastapi.APIRouter(
            dependencies=[
                fastapi.Depends(guard.require_session),
            ],
        )
        for path, handler in [
            (
                '/api/derivatives/underlyings',
                self.underlyings,
            ),
            (
                '/api/derivatives/expiries',
                self.expiries,
            ),
            (
                '/api/derivatives/chain',
                self.chain,
            ),
            (
                '/api/derivatives/surface',
                self.surface,
            ),
        ]:
            self.router.add_api_route(
                path,
                handler,
                methods=[
                    'GET',
                ],
            )

    async def underlyings(
        self,
        q: str = '',
        limit: int = 40,
    ) -> list[dict[str, Any]]:
        """Lists underlyings that have futures or options.

        Args:
            q (str): Typed text to match the start of the name.
            limit (int): The largest number of underlyings, from 1 to MAXIMUM_UNDERLYINGS.

        Returns:
            list[dict[str, Any]]: One entry per exchange and underlying.

        Raises:
            fastapi.HTTPException: 400 for an invalid limit, 503 while the index is not ready.
        """
        if limit < 1 or limit > MAXIMUM_UNDERLYINGS:
            raise fastapi.HTTPException(
                status_code=400,
                detail=f'The limit must be between 1 and {MAXIMUM_UNDERLYINGS}: {limit=}',
            )
        try:
            return await self.builder.underlyings(q, limit)
        except LookupError as error:
            raise fastapi.HTTPException(
                status_code=503,
                detail=str(error),
            ) from error

    async def expiries(self, exchange: str, underlying: str) -> dict[str, Any]:
        """Describes an underlying's cash instrument, futures and option expiries.

        Args:
            exchange (str): The exchange, such as "nse".
            underlying (str): The underlying, such as "NIFTY".

        Returns:
            dict[str, Any]: The description built by OptionChainBuilder.expiries.

        Raises:
            fastapi.HTTPException: 404 for an underlying without derivatives, 503 while the index is not ready.
        """
        try:
            return await self.builder.expiries(exchange, underlying.upper())
        except option_chain_builder.UnknownUnderlyingError as error:
            raise fastapi.HTTPException(
                status_code=404,
                detail=str(error),
            ) from error
        except LookupError as error:
            raise fastapi.HTTPException(
                status_code=503,
                detail=str(error),
            ) from error

    async def chain(
        self,
        exchange: str,
        underlying: str,
        expiry: str,
    ) -> dict[str, Any]:
        """Builds one expiry's option chain.

        Args:
            exchange (str): The exchange.
            underlying (str): The underlying.
            expiry (str): The expiry as "YYYY-MM-DD".

        Returns:
            dict[str, Any]: The chain built by OptionChainBuilder.chain.

        Raises:
            fastapi.HTTPException: 404 when there are no options for that expiry, 503 while the index is not ready.
        """
        try:
            return await self.builder.chain(
                exchange, underlying.upper(), expiry
            )
        except option_chain_builder.UnknownUnderlyingError as error:
            raise fastapi.HTTPException(
                status_code=404,
                detail=str(error),
            ) from error
        except LookupError as error:
            raise fastapi.HTTPException(
                status_code=503,
                detail=str(error),
            ) from error

    async def surface(self, exchange: str, underlying: str) -> dict[str, Any]:
        """Builds the underlying's implied volatility surface.

        Args:
            exchange (str): The exchange.
            underlying (str): The underlying.

        Returns:
            dict[str, Any]: The surface built by OptionChainBuilder.surface.

        Raises:
            fastapi.HTTPException: 404 for an underlying without derivatives, 503 while the index is not ready.
        """
        try:
            return await self.builder.surface(exchange, underlying.upper())
        except option_chain_builder.UnknownUnderlyingError as error:
            raise fastapi.HTTPException(
                status_code=404,
                detail=str(error),
            ) from error
        except LookupError as error:
            raise fastapi.HTTPException(
                status_code=503,
                detail=str(error),
            ) from error
