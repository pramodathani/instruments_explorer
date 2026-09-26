"""Checks that the unified broker interface answers and has a usable access token.

Typical usage example:

  checker = HealthChecker(gateway, token_source, clock)
  report = await checker.check()
"""

import asyncio
from typing import Any

from tradingmachine.ubi_client import exceptions
from tradingmachine.ubi_stores import stored_login_token_source

from instruments_explorer.unified_broker_interface import catalogue_gateway
from instruments_explorer.utilities import clock


class HealthChecker:
    """Reports on UBI in the same shape as the store checkers."""

    def __init__(
        self,
        client: catalogue_gateway.CatalogueGateway,
        token_source: stored_login_token_source.StoredLoginTokenSource,
        time_source: clock.SystemClock,
    ):
        """Creates the checker.

        Args:
            client (catalogue_gateway.CatalogueGateway): Calls UBI's greeting route.
            token_source (stored_login_token_source.StoredLoginTokenSource): tradingmachine's token source, which reads UBI's stored login.
            time_source (clock.SystemClock): The source of the current time.
        """
        self._client = client
        self._token_source = token_source
        self._time_source = time_source

    async def check(self) -> dict[str, Any]:
        """Calls UBI's greeting route and reads its stored login.

        Returns:
            dict[str, Any]: {"name", "reachable", "detail"}, where detail says until when the stored token is valid, or why UBI could not be reached.
        """
        try:
            await self._client.greeting()
        except exceptions.UnifiedBrokerInterfaceError as error:
            return {
                'name': 'ubi',
                'reachable': False,
                'detail': error.message,
            }
        detail = 'REST API answering'
        try:
            login = await asyncio.to_thread(self._token_source.stored_login)
        except exceptions.UnifiedBrokerInterfaceError:
            login = None
        if login is not None and login.is_usable(self._time_source.now(), 0):
            detail = f'token valid until {login.expires_at_text[:16]}'
        elif login is not None:
            detail = 'stored token expired; the next request connects'
        return {
            'name': 'ubi',
            'reachable': True,
            'detail': detail,
        }
