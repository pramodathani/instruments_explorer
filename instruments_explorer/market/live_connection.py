"""One browser's live WebSocket connection, with its queue of quotes to send.

Quotes are not sent the moment they arrive. The connection keeps only the newest quote per instrument and sends them together every quarter of a second, so a busy instrument ticking many times a second costs the browser one update per flush, and a slow browser never builds up a backlog.

Typical usage example:

  connection = LiveConnection('abc', websocket)
  sender = asyncio.create_task(connection.run_sender())
  connection.queue_quote(message)
"""

import asyncio
import logging
from typing import Any, Protocol

from instruments_explorer.utilities import clock

_LOGGER = logging.getLogger(__name__)
MAXIMUM_PENDING_EVENTS = 200


class MessageSocket(Protocol):
    """The part of a WebSocket the connection uses."""

    async def send_json(self, data: Any) -> None:
        """Sends one JSON message.

        Args:
            data (Any): The message.
        """

    async def close(self, code: int = 1000) -> None:
        """Closes the socket.

        Args:
            code (int): The close code.
        """


class LiveConnection:
    """Sends conflated quote batches, queued events and other messages to one browser.

    Attributes:
        connection_id: A unique id for the connection.
        flush_seconds: How often queued quotes are sent, in seconds.
        send_timeout_seconds: How long one send may take before the browser is dropped, in seconds.
        closed: Whether the connection has been closed.
    """

    def __init__(
        self,
        connection_id: str,
        websocket: MessageSocket,
        time_source: clock.SystemClock,
        flush_seconds: float = 0.25,
        send_timeout_seconds: float = 5.0,
    ):
        """Creates the connection.

        Args:
            connection_id (str): A unique id for the connection.
            websocket (MessageSocket): The accepted WebSocket.
            time_source (clock.SystemClock): The source of the server time sent with each batch.
            flush_seconds (float): How often queued quotes are sent, in seconds.
            send_timeout_seconds (float): How long one send may take before the browser is dropped, in seconds.
        """
        self.connection_id = connection_id
        self.flush_seconds = flush_seconds
        self.send_timeout_seconds = send_timeout_seconds
        self.closed = False
        self._websocket = websocket
        self._time_source = time_source
        self._pending_quotes = {}
        self._pending_events = []
        self._send_lock = asyncio.Lock()

    def queue_quote(self, message: dict[str, Any]) -> None:
        """Queues a quote, replacing any quote for the same instrument not yet sent.

        Args:
            message (dict[str, Any]): An encoded quote with "instrument_id".
        """
        if self.closed:
            return
        self._pending_quotes[message['instrument_id']] = message

    def queue_event(self, message: dict[str, Any]) -> None:
        """Queues a message that is not a quote, such as a fetch job's progress, to be sent with the next flush.

        Only the newest 200 events are kept for a browser that has fallen behind.

        Args:
            message (dict[str, Any]): The message, with "type".
        """
        if self.closed:
            return
        self._pending_events.append(message)
        if len(self._pending_events) > MAXIMUM_PENDING_EVENTS:
            del self._pending_events[0]

    def pending_count(self) -> int:
        """Counts the instruments with a quote waiting to be sent.

        Returns:
            int: The number of queued quotes.
        """
        return len(self._pending_quotes)

    async def flush(self) -> bool:
        """Sends every queued event, then every queued quote as one message.

        Returns:
            bool: True when the send succeeded or there was nothing to send, False when the browser was dropped.
        """
        if self.closed:
            return False
        events = self._pending_events
        self._pending_events = []
        for event in events:
            if not await self.send(event):
                return False
        if not self._pending_quotes:
            return True
        quotes = list(self._pending_quotes.values())
        self._pending_quotes = {}
        message = {
            'type': 'quotes',
            'server_time': self._time_source.now(),
            'quotes': quotes,
        }
        return await self.send(message)

    async def send(self, message: dict[str, Any]) -> bool:
        """Sends one message, dropping the browser if the send is too slow or fails.

        Every failure is caught, because a browser that has gone away raises whatever the server library raises for a closed socket, and one browser leaving must never stop the others being served.

        Args:
            message (dict[str, Any]): The message.

        Returns:
            bool: True when the message was sent, False when the connection is now closed.
        """
        if self.closed:
            return False
        async with self._send_lock:
            try:
                await asyncio.wait_for(
                    self._websocket.send_json(message),
                    timeout=self.send_timeout_seconds,
                )
            except Exception as error:  # noqa: BLE001
                _LOGGER.info(
                    'Dropping live connection %s: %s',
                    self.connection_id,
                    error,
                )
                await self.close()
                return False
        return True

    async def run_sender(self) -> None:
        """Flushes queued quotes every flush interval until the connection closes."""
        while not self.closed:
            await asyncio.sleep(self.flush_seconds)
            await self.flush()

    async def close(self) -> None:
        """Closes the connection once; later calls do nothing."""
        if self.closed:
            return
        self.closed = True
        self._pending_quotes = {}
        self._pending_events = []
        try:
            await self._websocket.close(code=1011)
        except Exception as error:  # noqa: BLE001
            _LOGGER.debug(
                'The live connection %s was already gone when closing: %s',
                self.connection_id,
                error,
            )
