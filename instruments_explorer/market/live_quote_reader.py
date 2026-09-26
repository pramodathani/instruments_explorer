"""Reads the latest quote of every watched instrument from UBI's live quote hash.

UBI keeps the newest unified quote of each instrument in the Redis hash `unified:quotes:live`. Reading the hash asks only for the instruments somebody is looking at, so the work depends on what is on screen rather than on how busy the market is.

Typical usage example:

  reader = LiveQuoteReader(redis_source, hub)
  task = asyncio.create_task(reader.run())
"""

import asyncio
import logging

import redis

from instruments_explorer.market import live_quote_hub
from instruments_explorer.unified_broker_interface import redis_reader

_LOGGER = logging.getLogger(__name__)
LIVE_QUOTES_HASH = 'unified:quotes:live'


class LiveQuoteReader:
    """Asks UBI's live quote hash about the watched instruments, over and over.

    Attributes:
        interval_seconds: How long to wait between one read and the next, in seconds.
        batch_size: The most instruments asked about in one Redis call.
        retry_seconds: How long to wait after Redis fails, in seconds.
    """

    def __init__(
        self,
        quote_redis_reader: redis_reader.RedisReader,
        hub: live_quote_hub.LiveQuoteHub,
        interval_seconds: float = 0.5,
        batch_size: int = 500,
        retry_seconds: float = 3.0,
    ):
        """Creates the reader.

        Args:
            quote_redis_reader (redis_reader.RedisReader): Reads UBI's Redis.
            hub (live_quote_hub.LiveQuoteHub): Knows the watched instruments and receives the quotes.
            interval_seconds (float): How long to wait between one read and the next, in seconds.
            batch_size (int): The most instruments asked about in one Redis call.
            retry_seconds (float): How long to wait after Redis fails, in seconds.
        """
        self.interval_seconds = interval_seconds
        self.batch_size = batch_size
        self.retry_seconds = retry_seconds
        self._redis_reader = quote_redis_reader
        self._hub = hub

    async def run(self) -> None:
        """Reads the watched instruments' quotes again and again until cancelled."""
        while True:
            try:
                await self.read_once()
            except (redis.RedisError, OSError) as error:
                _LOGGER.warning('Could not read UBI live quotes: %s', error)
                await asyncio.sleep(self.retry_seconds)
            else:
                await asyncio.sleep(self.interval_seconds)

    async def read_once(self) -> int:
        """Reads every watched instrument's newest quote and delivers the ones that have changed.

        Returns:
            int: The number of quotes delivered.

        Raises:
            redis.RedisError: Redis could not be read.
        """
        watched = sorted(self._hub.watched_ids())
        delivered = 0
        for start in range(0, len(watched), self.batch_size):
            batch = watched[start : start + self.batch_size]
            documents = await self._redis_reader.hash_get_many_json(
                LIVE_QUOTES_HASH,
                batch,
            )
            for document in documents.values():
                if not isinstance(document, dict):
                    continue
                instrument_id = document.get('instrument_id')
                if not isinstance(instrument_id, str):
                    continue
                previous = self._hub.latest_received_at(instrument_id)
                if previous is not None and previous == document.get(
                    'received_at'
                ):
                    continue
                self._hub.deliver(document, 'live')
                delivered += 1
        return delivered
