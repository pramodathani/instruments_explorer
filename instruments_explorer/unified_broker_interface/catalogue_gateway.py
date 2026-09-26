"""Reads UBI through tradingmachine's catalogue without blocking the event loop.

tradingmachine sends its requests with the blocking requests library. This gateway runs each call in a worker thread and offers the same async methods, answers and errors the rest of the project has always used, so routes, jobs and the assistant need not know that tradingmachine is underneath.

Typical usage example:

  gateway = CatalogueGateway(components.catalogue)
  document = await gateway.prices(instrument_id, 'day', 365, True)
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from tradingmachine.ubi_client import instrument_catalogue

DEFAULT_BATCH_SIZE = 5000


class CatalogueGateway:
    """UBI's instruments, quotes, candles and instrument master, read in worker threads."""

    def __init__(self, catalogue: instrument_catalogue.InstrumentCatalogue):
        """Creates the gateway.

        Args:
            catalogue (instrument_catalogue.InstrumentCatalogue): tradingmachine's catalogue over the shared client.
        """
        self._catalogue = catalogue

    async def greeting(self) -> Any:
        """Calls UBI's greeting route, which needs no token, to show whether UBI is running.

        Returns:
            Any: UBI's welcome document.

        Raises:
            UnifiedBrokerInterfaceError: UBI could not be reached or answered with a failure status.
        """
        return await asyncio.to_thread(self._read_greeting)

    async def instrument_segments(self) -> Any:
        """Lists UBI's segments with the current mapping date.

        Returns:
            Any: A document with "mapping_date", "exchanges" and "segments".

        Raises:
            UnifiedBrokerInterfaceError: The request failed.
        """
        return await asyncio.to_thread(self._read_segments)

    async def download_master(
        self,
        handle_batch: Callable[[list[dict[str, Any]]], Awaitable[None]],
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> str:
        """Streams every instrument of the current catalogue, in batches.

        Each batch is read in a worker thread and then handed on in the event loop, so the whole catalogue is never held at once.

        Args:
            handle_batch (Callable[[list[dict[str, Any]]], Awaitable[None]]): Called with each batch of identity documents, in catalogue order.
            batch_size (int): How many instruments each batch holds, except the last.

        Returns:
            str: The catalogue's mapping date, from the X-Mapping-Date header.

        Raises:
            IncompleteResponseError: The answer stopped before its end or has no mapping date.
            UnifiedBrokerInterfaceError: The token could not be found, UBI could not be reached, or UBI answered with a failure status.
        """
        stream = await asyncio.to_thread(self._catalogue.open_master)
        try:
            while True:
                batch = await asyncio.to_thread(stream.next_batch, batch_size)
                if batch is None:
                    break
                await handle_batch(batch)
        finally:
            stream.close()
        return stream.mapping_date

    async def instrument_details(self, instrument_id: str) -> Any:
        """Reads an instrument's identity, seen dates, lot size, tick size and broker handles.

        Args:
            instrument_id (str): UBI's instrument id.

        Returns:
            Any: The instrument details document.

        Raises:
            UnifiedBrokerInterfaceError: The request failed.
        """
        return await asyncio.to_thread(self._catalogue.details, instrument_id)

    async def additional_details(self, instrument_id: str) -> Any:
        """Reads the extra attributes each broker publishes about an instrument, such as its ISIN.

        Args:
            instrument_id (str): UBI's instrument id.

        Returns:
            Any: A document with "attribute_names" and one "carried_by" entry per broker.

        Raises:
            UnifiedBrokerInterfaceError: The request failed.
        """
        return await asyncio.to_thread(
            self._catalogue.additional_details,
            instrument_id,
        )

    async def quote(self, instrument_id: str) -> Any:
        """Reads an instrument's full quote with market depth.

        Args:
            instrument_id (str): UBI's instrument id.

        Returns:
            Any: The unified quote document with "source".

        Raises:
            UnifiedBrokerInterfaceError: The request failed.
        """
        return await asyncio.to_thread(self._catalogue.quote, instrument_id)

    async def prices(
        self,
        instrument_id: str,
        interval: str,
        days: int,
        adjusted: bool,
    ) -> Any:
        """Reads an instrument's stored candles for the last so many days.

        Args:
            instrument_id (str): UBI's instrument id.
            interval (str): The candle length, such as "day" or "5minute".
            days (int): How many days back from today to read.
            adjusted (bool): Whether to correct an adjustable instrument's prices for splits and bonuses.

        Returns:
            Any: UBI's prices document unchanged, with "columns", "candles", "price_basis", "adjustable", "source" and "to".

        Raises:
            UnifiedBrokerInterfaceError: The request failed.
        """
        return await asyncio.to_thread(
            self._read_prices,
            instrument_id,
            interval,
            days,
            adjusted,
        )

    def _read_greeting(self) -> Any:
        """Reads the greeting in the calling thread.

        Returns:
            Any: UBI's welcome document.

        Raises:
            UnifiedBrokerInterfaceError: UBI could not be reached or answered with a failure status.
        """
        return self._catalogue.greeting

    def _read_segments(self) -> Any:
        """Reads the segments in the calling thread.

        Returns:
            Any: A document with "mapping_date", "exchanges" and "segments".

        Raises:
            UnifiedBrokerInterfaceError: The request failed.
        """
        return self._catalogue.segments

    def _read_prices(
        self,
        instrument_id: str,
        interval: str,
        days: int,
        adjusted: bool,
    ) -> Any:
        """Reads the prices document in the calling thread.

        Args:
            instrument_id (str): UBI's instrument id.
            interval (str): The candle length.
            days (int): How many days back from today to read.
            adjusted (bool): Whether to adjust for splits and bonuses.

        Returns:
            Any: UBI's prices document unchanged.

        Raises:
            UnifiedBrokerInterfaceError: The request failed.
        """
        document = self._catalogue.prices_document(
            instrument_id,
            interval=interval,
            days=days,
            adjusted=adjusted,
        )
        return document.document
