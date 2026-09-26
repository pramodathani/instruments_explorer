"""Reads many instruments' live quotes through tradingmachine without blocking the event loop.

Typical usage example:

  gateway = LiveQuoteGateway(components.live_quote_reader)
  quotes = await gateway.read(['id-a', 'id-b'])
"""

import asyncio
from collections.abc import Sequence

from tradingmachine.ubi_stores import live_quote_reader


class LiveQuoteGateway:
    """UBI's live quote hash, read in a worker thread."""

    def __init__(self, reader: live_quote_reader.LiveQuoteReader):
        """Creates the gateway.

        Args:
            reader (live_quote_reader.LiveQuoteReader): tradingmachine's reader of UBI's live quote hash.
        """
        self._reader = reader

    async def read(self, instrument_ids: Sequence[str]) -> dict[str, dict]:
        """Reads the live quotes of the given instruments.

        Args:
            instrument_ids (Sequence[str]): UBI instrument ids.

        Returns:
            dict[str, dict]: UBI's unified quote by instrument id, for those that have one.

        Raises:
            UnreachableError: UBI's Redis could not be read.
        """
        return await asyncio.to_thread(self._reader.read, list(instrument_ids))
