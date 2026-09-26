"""The WebSocket that sends live quotes to the browser.

The browser sends {"type": "subscribe", "instrument_ids": [...]}, {"type": "unsubscribe", ...} or {"type": "ping"}, and receives {"type": "quotes", "quotes": [...]} batches, "pong" and "error" messages.

Typical usage example:

  web_application.include_router(
      LiveRoutes(hub, guard, origin_checker).router
  )
"""

import asyncio
import contextlib
import uuid
from typing import Any

import fastapi
import starlette.websockets

from instruments_explorer.market import live_connection
from instruments_explorer.market import live_quote_hub
from instruments_explorer.security import session_guard
from instruments_explorer.security import websocket_origin_checker
from instruments_explorer.utilities import clock

_POLICY_VIOLATION = 1008


class LiveRoutes:
    """The /api/live WebSocket route.

    Attributes:
        hub: Tracks subscriptions and delivers quotes.
        guard: Checks the session.
        origin_checker: Refuses connections from other sites' pages.
        time_source: The source of the server time sent with messages.
        router: The FastAPI router holding the route.
    """

    def __init__(
        self,
        hub: live_quote_hub.LiveQuoteHub,
        guard: session_guard.SessionGuard,
        origin_checker: websocket_origin_checker.WebsocketOriginChecker,
        time_source: clock.SystemClock,
    ):
        """Creates the route.

        Args:
            hub (live_quote_hub.LiveQuoteHub): Tracks subscriptions and delivers quotes.
            guard (session_guard.SessionGuard): Checks the session.
            origin_checker (websocket_origin_checker.WebsocketOriginChecker): Refuses connections from other sites' pages.
            time_source (clock.SystemClock): The source of the server time sent with messages.
        """
        self.hub = hub
        self.guard = guard
        self.origin_checker = origin_checker
        self.time_source = time_source
        self.router = fastapi.APIRouter()
        self.router.add_api_websocket_route('/api/live', self.live)

    async def live(self, websocket: fastapi.WebSocket) -> None:
        """Serves one browser's live connection until it closes.

        Args:
            websocket (fastapi.WebSocket): The WebSocket being opened.
        """
        if not self.origin_checker.is_allowed(websocket.headers):
            await websocket.close(code=_POLICY_VIOLATION)
            return
        if not self.guard.is_logged_in(websocket):
            await websocket.close(code=_POLICY_VIOLATION)
            return
        await websocket.accept()
        connection = live_connection.LiveConnection(
            uuid.uuid4().hex,
            websocket,
            self.time_source,
        )
        self.hub.add_connection(connection)
        sender = asyncio.create_task(connection.run_sender())
        try:
            while not connection.closed:
                message = await websocket.receive_json()
                await self._handle(connection, message)
        except (
            starlette.websockets.WebSocketDisconnect,
            RuntimeError,
            ValueError,
        ):
            pass
        finally:
            sender.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sender
            self.hub.remove_connection(connection.connection_id)
            await connection.close()

    async def _handle(
        self,
        connection: live_connection.LiveConnection,
        message: Any,
    ) -> None:
        """Acts on one message from the browser.

        Args:
            connection (live_connection.LiveConnection): The browser's connection.
            message (Any): The parsed JSON message.
        """
        if not isinstance(message, dict):
            await self._refuse(connection, 'A message must be a JSON object.')
            return
        message_type = message.get('type')
        if message_type == 'ping':
            await connection.send(
                {
                    'type': 'pong',
                    'server_time': self.time_source.now(),
                }
            )
            return
        if message_type not in ('subscribe', 'unsubscribe'):
            await self._refuse(
                connection, f'Unknown message type: {message_type!r}'
            )
            return
        instrument_ids = message.get('instrument_ids')
        valid_ids = isinstance(instrument_ids, list)
        if valid_ids:
            for instrument_id in instrument_ids:
                if not isinstance(instrument_id, str):
                    valid_ids = False
        if not valid_ids:
            await self._refuse(
                connection, 'instrument_ids must be a list of strings.'
            )
            return
        if message_type == 'unsubscribe':
            self.hub.unsubscribe(connection.connection_id, instrument_ids)
            return
        try:
            self.hub.subscribe(connection.connection_id, instrument_ids)
        except ValueError as error:
            await self._refuse(connection, str(error))

    async def _refuse(
        self,
        connection: live_connection.LiveConnection,
        explanation: str,
    ) -> None:
        """Tells the browser a message was refused.

        Args:
            connection (live_connection.LiveConnection): The browser's connection.
            explanation (str): Why the message was refused.
        """
        await connection.send(
            {
                'type': 'error',
                'message': explanation,
            }
        )
