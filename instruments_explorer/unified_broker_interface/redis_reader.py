"""Read-only access to UBI's Redis.

The reader exposes only commands that read. Nothing in instruments_explorer writes to UBI's Redis.

Typical usage example:

  reader = RedisReader.from_configuration(configuration, timeout_seconds=3)
  document = await reader.hash_get_json('last_login', 'unified_broker_interface')
"""

import json
import time
from typing import Any, Self

import redis.asyncio

from instruments_explorer.configuration import (
    unified_broker_interface_configuration,
)


class RedisReader:
    """Reads strings and hashes from UBI's Redis without ever writing."""

    def __init__(self, client: redis.asyncio.Redis):
        """Wraps an asynchronous Redis client that decodes responses to text.

        Args:
            client (redis.asyncio.Redis): A client created with decode_responses=True.
        """
        self._client = client

    @classmethod
    def from_configuration(
        cls,
        configuration: (
            unified_broker_interface_configuration.UnifiedBrokerInterfaceConfiguration
        ),
        timeout_seconds: float,
    ) -> Self:
        """Creates a reader for UBI's Redis.

        Args:
            configuration (UnifiedBrokerInterfaceConfiguration): UBI's store addresses and credentials.
            timeout_seconds (float): How long a command may take before it fails.

        Returns:
            Self: The reader. It connects on its first command.
        """
        client = redis.asyncio.Redis(
            host=configuration.redis_host,
            port=configuration.redis_port,
            db=configuration.redis_database,
            username=configuration.redis_username,
            password=configuration.redis_password,
            decode_responses=True,
            socket_timeout=timeout_seconds,
            socket_connect_timeout=timeout_seconds,
        )
        return cls(client)

    async def ping_milliseconds(self) -> float:
        """Measures how long Redis takes to answer a PING.

        Returns:
            float: The round trip in milliseconds.

        Raises:
            redis.RedisError: Redis could not be reached.
        """
        started = time.perf_counter()
        await self._client.ping()
        return (time.perf_counter() - started) * 1000

    async def hash_get_text(self, key: str, field: str) -> str | None:
        """Reads one field of a hash.

        Args:
            key (str): The hash key.
            field (str): The field.

        Returns:
            str | None: The value, or None when the key or field does not exist.

        Raises:
            redis.RedisError: Redis could not be read.
        """
        return await self._client.hget(key, field)

    async def hash_get_json(self, key: str, field: str) -> Any:
        """Reads one field of a hash that holds a JSON document.

        Args:
            key (str): The hash key.
            field (str): The field.

        Returns:
            Any: The parsed document, or None when the key or field does not exist.

        Raises:
            redis.RedisError: Redis could not be read.
            ValueError: The value is not valid JSON.
        """
        text = await self.hash_get_text(key, field)
        if text is None:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            raise ValueError(
                f'Not valid JSON in Redis at {key} {field}'
            ) from error

    async def hash_get_many_json(
        self,
        key: str,
        fields: list[str],
    ) -> dict[str, Any]:
        """Reads several fields of a hash that hold JSON documents, in one round trip.

        Args:
            key (str): The hash key.
            fields (list[str]): The fields.

        Returns:
            dict[str, Any]: The parsed document of each field that exists and holds valid JSON.

        Raises:
            redis.RedisError: Redis could not be read.
        """
        if not fields:
            return {}
        texts = await self._client.hmget(key, fields)
        documents = {}
        for field, text in zip(fields, texts, strict=True):
            if text is None:
                continue
            try:
                documents[field] = json.loads(text)
            except json.JSONDecodeError:
                continue
        return documents

    async def stream_read(
        self,
        key: str,
        last_id: str,
        count: int,
        block_milliseconds: int,
    ) -> list[tuple[str, dict[str, str]]]:
        """Reads the entries of a stream that came after an id, waiting for new ones.

        This is XREAD, which reads without a consumer group, so it changes nothing in Redis.

        Args:
            key (str): The stream key.
            last_id (str): The last entry already read, or "$" for only entries added from now on.
            count (int): The largest number of entries to return.
            block_milliseconds (int): How long to wait for an entry when there is none, in milliseconds.

        Returns:
            list[tuple[str, dict[str, str]]]: A list of tuples (entry id, entry fields), oldest first, empty when nothing arrived in time.

        Raises:
            redis.RedisError: Redis could not be read.
        """
        reply = await self._client.xread(
            {
                key: last_id,
            },
            count=count,
            block=block_milliseconds,
        )
        entries = []
        for _, stream_entries in reply or []:
            for entry_id, fields in stream_entries:
                entries.append((entry_id, fields))
        return entries

    async def close(self) -> None:
        """Closes the connection pool."""
        await self._client.aclose()
