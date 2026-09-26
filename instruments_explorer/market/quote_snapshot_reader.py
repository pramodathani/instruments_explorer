"""Reads the latest quotes of many instruments at once from UBI's live quote hash.

An option chain or a volatility surface needs hundreds of quotes at a time, which one call per contract to UBI's REST quote route would make slow and could push onto brokers. The live hash answers them all in a few milliseconds.

Typical usage example:

  reader = QuoteSnapshotReader(quote_gateway)
  quotes = await reader.read(['id-a', 'id-b'])
"""

import logging
from collections.abc import Sequence
from typing import Any

from tradingmachine.ubi_client import exceptions

from instruments_explorer.unified_broker_interface import live_quote_gateway

_LOGGER = logging.getLogger(__name__)


class QuoteSnapshotReader:
    """Reads many instruments' latest quotes, never failing the caller when Redis is down."""

    def __init__(self, quote_gateway: live_quote_gateway.LiveQuoteGateway):
        """Creates the reader.

        Args:
            quote_gateway (live_quote_gateway.LiveQuoteGateway): Reads UBI's live quote hash through tradingmachine, which batches the instruments.
        """
        self._quote_gateway = quote_gateway

    async def read(self, instrument_ids: Sequence[str]) -> dict[str, Any]:
        """Reads the latest quote of each instrument the hash holds.

        Args:
            instrument_ids (Sequence[str]): The instruments.

        Returns:
            dict[str, Any]: UBI's unified quote by instrument id, for those that have one; empty when Redis could not be read.
        """
        try:
            documents = await self._quote_gateway.read(instrument_ids)
        except exceptions.UnreachableError as error:
            _LOGGER.warning('Could not read UBI live quotes: %s', error)
            return {}
        quotes = {}
        for instrument_id, document in documents.items():
            if isinstance(document, dict):
                quotes[instrument_id] = document
        return quotes
