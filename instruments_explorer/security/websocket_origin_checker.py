"""Refuses WebSocket connections opened by pages from another site.

Browsers send cookies with a WebSocket upgrade from any page, and cross-site WebSockets are not protected by CORS, so a page on another site could otherwise open instruments_explorer's live feed with the user's session. Browsers always send an Origin header with a WebSocket upgrade, and a page cannot forge it, so the origin's host must match the Host the browser connected to.

Typical usage example:

  if not WebsocketOriginChecker().is_allowed(websocket.headers):
      await websocket.close(code=1008)
"""

import urllib.parse
from collections.abc import Mapping


class WebsocketOriginChecker:
    """Compares a WebSocket upgrade's Origin header with its Host header."""

    def is_allowed(self, headers: Mapping[str, str]) -> bool:
        """Checks whether a WebSocket upgrade came from instruments_explorer's own pages.

        Args:
            headers (Mapping[str, str]): The upgrade request's headers, with lower-case names.

        Returns:
            bool: True when the Origin header's host and port equal the Host header.
        """
        origin = headers.get('origin')
        host = headers.get('host')
        if not origin or not host:
            return False
        origin_host = urllib.parse.urlsplit(origin).netloc
        return origin_host.lower() == host.lower()
