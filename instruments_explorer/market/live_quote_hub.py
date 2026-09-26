"""The centre of live prices: which browser watches which instrument, the latest quote of each, and delivery.

Typical usage example:

  hub = LiveQuoteHub()
  hub.add_connection(connection)
  hub.subscribe(connection.connection_id, ['id-a'])
  hub.deliver(quote, 'live')
"""

from collections.abc import Mapping
from typing import Any

from instruments_explorer.market import live_connection
from instruments_explorer.market import quote_encoder

MAXIMUM_SUBSCRIPTIONS_PER_CONNECTION = 300


class LiveQuoteHub:
    """Tracks subscriptions and hands each new quote to the browsers watching its instrument."""

    def __init__(self):
        """Creates an empty hub."""
        self._encoder = quote_encoder.QuoteEncoder()
        self._connections = {}
        self._subscriptions = {}
        self._latest_quotes = {}

    def add_connection(
        self, connection: live_connection.LiveConnection
    ) -> None:
        """Starts serving a browser.

        Args:
            connection (live_connection.LiveConnection): The browser's connection.
        """
        self._connections[connection.connection_id] = connection
        self._subscriptions[connection.connection_id] = set()

    def remove_connection(self, connection_id: str) -> None:
        """Stops serving a browser and forgets quotes nobody watches any more.

        Args:
            connection_id (str): The connection's id.
        """
        self._connections.pop(connection_id, None)
        self._subscriptions.pop(connection_id, None)
        self._forget_unwatched()

    def subscribe(self, connection_id: str, instrument_ids: list[str]) -> None:
        """Starts sending a browser the quotes of some instruments, beginning with the latest one known.

        Args:
            connection_id (str): The connection's id.
            instrument_ids (list[str]): The instruments to watch.

        Raises:
            ValueError: The connection is unknown, or would watch more than MAXIMUM_SUBSCRIPTIONS_PER_CONNECTION instruments.
        """
        watched = self._subscriptions.get(connection_id)
        if watched is None:
            raise ValueError(f'Unknown live connection: {connection_id!r}')
        combined = watched.union(instrument_ids)
        if len(combined) > MAXIMUM_SUBSCRIPTIONS_PER_CONNECTION:
            raise ValueError(
                f'A connection may watch at most {MAXIMUM_SUBSCRIPTIONS_PER_CONNECTION} instruments.'
            )
        self._subscriptions[connection_id] = combined
        connection = self._connections[connection_id]
        for instrument_id in instrument_ids:
            latest = self._latest_quotes.get(instrument_id)
            if latest is not None:
                connection.queue_quote(latest)

    def unsubscribe(
        self, connection_id: str, instrument_ids: list[str]
    ) -> None:
        """Stops sending a browser the quotes of some instruments.

        Args:
            connection_id (str): The connection's id.
            instrument_ids (list[str]): The instruments to stop watching.
        """
        watched = self._subscriptions.get(connection_id)
        if watched is None:
            return
        watched.difference_update(instrument_ids)
        self._forget_unwatched()

    def watched_ids(self) -> set[str]:
        """Lists every instrument some browser watches.

        Returns:
            set[str]: The instrument ids.
        """
        watched = set()
        for instrument_ids in self._subscriptions.values():
            watched.update(instrument_ids)
        return watched

    def latest_received_at(self, instrument_id: str) -> float | None:
        """Finds when the latest delivered quote of an instrument reached UBI.

        Args:
            instrument_id (str): The instrument's id.

        Returns:
            float | None: The quote's "received_at", or None when no quote has been delivered.
        """
        latest = self._latest_quotes.get(instrument_id)
        if latest is None:
            return None
        return latest.get('received_at')

    def deliver(self, quote: Mapping[str, Any], source: str) -> None:
        """Encodes a quote, keeps it as the latest, and queues it for every browser watching.

        Args:
            quote (Mapping[str, Any]): UBI's unified quote.
            source (str): Where the quote came from, such as "live".
        """
        instrument_id = quote.get('instrument_id')
        if not isinstance(instrument_id, str):
            return
        message = self._encoder.encode(quote, source)
        self._latest_quotes[instrument_id] = message
        for connection_id, watched in self._subscriptions.items():
            if instrument_id in watched:
                self._connections[connection_id].queue_quote(message)

    def broadcast_event(self, message: dict[str, Any]) -> None:
        """Queues a message that is not a quote, such as a fetch job's progress, for every open browser.

        Args:
            message (dict[str, Any]): The message, with "type".
        """
        for connection in self._connections.values():
            connection.queue_event(message)

    def connection_count(self) -> int:
        """Counts the browsers being served.

        Returns:
            int: The number of connections.
        """
        return len(self._connections)

    def _forget_unwatched(self) -> None:
        """Drops the latest quotes of instruments nobody watches."""
        watched = self.watched_ids()
        for instrument_id in list(self._latest_quotes):
            if instrument_id not in watched:
                del self._latest_quotes[instrument_id]
