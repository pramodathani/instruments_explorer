"""The connection to the project's own ChromaDB server.

Typical usage example:

  connection = ChromaConnection(explorer_settings)
  report = await connection.check()
  await connection.close()
"""

from typing import Any

import httpx

from instruments_explorer.configuration import settings


class ChromaConnection:
    """Reaches the ChromaDB server over its HTTP API.

    Attributes:
        base_url: The server's base address.
    """

    def __init__(self, explorer_settings: settings.Settings):
        """Creates the HTTP client without connecting yet.

        Args:
            explorer_settings (settings.Settings): Supplies the address and timeout.
        """
        self.base_url = explorer_settings.chromadb_url()
        self._http_client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=explorer_settings.store_timeout_seconds,
        )

    async def check(self) -> dict[str, Any]:
        """Asks ChromaDB for its heartbeat and version.

        Returns:
            dict[str, Any]: {"name", "reachable", "detail"}, where detail is the server version or the reason it could not be reached.
        """
        try:
            response = await self._http_client.get('/api/v2/version')
            response.raise_for_status()
        except httpx.HTTPError as error:
            return {
                'name': 'ChromaDB',
                'reachable': False,
                'detail': str(error) or type(error).__name__,
            }
        return {
            'name': 'ChromaDB',
            'reachable': True,
            'detail': f'API version {response.json()}',
        }

    async def close(self) -> None:
        """Closes the HTTP client."""
        await self._http_client.aclose()
