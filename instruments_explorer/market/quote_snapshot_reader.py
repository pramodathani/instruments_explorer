"""Reads the latest quotes of many instruments at once from UBI's live quote hash.

An option chain or a volatility surface needs hundreds of quotes at a time, which one call per contract to UBI's REST quote route would make slow and could push onto brokers. The live hash answers them all in a few milliseconds.

Typical usage example:

  reader = QuoteSnapshotReader(redis_source)
  quotes = await reader.read(['id-a', 'id-b'])
"""

import logging
from collections.abc import Sequence
from typing import Any

import redis

from instruments_explorer.unified_broker_interface import redis_reader

_LOGGER = logging.getLogger(__name__)
LIVE_QUOTES_HASH = 'unified:quotes:live'
_BATCH_SIZE = 500


class QuoteSnapshotReader:
    """Reads many instruments' latest quotes, never failing the caller when Redis is down."""

    def __init__(self, quote_redis_reader: redis_reader.RedisReader):
        """Creates the reader.

        Args:
            quote_redis_reader (redis_reader.RedisReader): Reads UBI's Redis.
        """
        self._redis_reader = quote_redis_reader

    async def read(self, instrument_ids: Sequence[str]) -> dict[str, Any]:
        """Reads the latest quote of each instrument the hash holds.

        Args:
            instrument_ids (Sequence[str]): The instruments.

        Returns:
            dict[str, Any]: UBI's unified quote by instrument id, for those that have one; empty when Redis could not be read.
        """
        quotes = {}
        unique_ids = list(dict.fromkeys(instrument_ids))
        for start in range(0, len(unique_ids), _BATCH_SIZE):
            batch = unique_ids[start : start + _BATCH_SIZE]
            try:
                documents = await self._redis_reader.hash_get_many_json(
                    LIVE_QUOTES_HASH,
                    batch,
                )
            except (redis.RedisError, OSError) as error:
                _LOGGER.warning('Could not read UBI live quotes: %s', error)
                return {}
            for instrument_id, document in documents.items():
                if isinstance(document, dict):
                    quotes[instrument_id] = document
        return quotes
