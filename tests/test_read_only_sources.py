"""Tests that instruments_explorer can only read UBI's Redis and MongoDB."""

import asyncio
import inspect
import re
from pathlib import Path
from typing import Any

import pytest

from instruments_explorer.unified_broker_interface import mongo_reader
from instruments_explorer.unified_broker_interface import redis_reader

_SOURCE_DIRECTORY = (
    Path(__file__).resolve().parent.parent / 'instruments_explorer'
)
_FILES_ALLOWED_TO_USE_STORES = [
    'market/live_quote_reader.py',
    'unified_broker_interface/access_token_provider.py',
    'unified_broker_interface/mongo_reader.py',
    'unified_broker_interface/redis_reader.py',
]
_OWN_STORE_DIRECTORY = 'storage/'
_STORE_IMPORT = re.compile(r'^(import|from) (redis|pymongo)\b')

_WRITE_CALL = re.compile(
    r'\.(set|hset|hsetnx|hmset|hdel|delete|unlink|expire|sadd|srem|'
    r'lpush|rpush|xadd|xgroup_create|xack|xtrim|incr|decr|publish|'
    r'insert_one|insert_many|update_one|update_many|replace_one|'
    r'delete_one|delete_many|find_one_and_update|drop)\('
)


class _FakeRedisClient:
    """A stand-in for redis.asyncio.Redis holding one hash."""

    def __init__(self, hashes: dict[str, dict[str, str]]):
        """Creates the client.

        Args:
            hashes (dict[str, dict[str, str]]): Hash contents by key and field.
        """
        self.hashes = hashes

    async def hget(self, key: str, field: str) -> str | None:
        """Reads a hash field.

        Args:
            key (str): The hash key.
            field (str): The field.

        Returns:
            str | None: The value, or None.
        """
        return self.hashes.get(key, {}).get(field)


class _FakeCollection:
    """A stand-in for a MongoDB collection holding documents."""

    def __init__(self, documents: list[dict[str, Any]]):
        """Creates the collection.

        Args:
            documents (list[dict[str, Any]]): The documents.
        """
        self.documents = documents

    def find_one(
        self,
        query: dict[str, Any],
        projection: dict[str, int],
    ) -> dict[str, Any] | None:
        """Finds the first document matching every query field.

        Args:
            query (dict[str, Any]): Field values to match.
            projection (dict[str, int]): Fields to leave out when set to 0.

        Returns:
            dict[str, Any] | None: A copy of the matching document, or None.
        """
        for document in self.documents:
            matches = True
            for field_name, value in query.items():
                if document.get(field_name) != value:
                    matches = False
            if matches:
                result = dict(document)
                for field_name, included in projection.items():
                    if included == 0:
                        result.pop(field_name, None)
                return result
        return None


class TestReadOnlySources:
    """Tests for RedisReader, MongoReader and the source tree."""

    def test_redis_reader_has_no_write_methods(self) -> None:
        """Checks that the Redis reader's public methods all read."""
        public_methods = set()
        for name, _ in inspect.getmembers(redis_reader.RedisReader):
            if not name.startswith('_'):
                public_methods.add(name)
        assert public_methods == {
            'close',
            'from_configuration',
            'hash_get_json',
            'hash_get_many_json',
            'hash_get_text',
            'ping_milliseconds',
            'stream_read',
        }

    def test_mongo_reader_has_no_write_methods(self) -> None:
        """Checks that the MongoDB reader's public methods all read."""
        public_methods = set()
        for name, _ in inspect.getmembers(mongo_reader.MongoReader):
            if not name.startswith('_'):
                public_methods.add(name)
        assert public_methods == {
            'api_credentials',
            'close',
            'from_configuration',
            'stored_login',
        }

    def test_only_known_files_use_redis_or_mongodb(self) -> None:
        """Checks that only the reviewed files and the project's own storage package import a Redis or MongoDB client."""
        importing_files = []
        for path in sorted(_SOURCE_DIRECTORY.rglob('*.py')):
            relative = path.relative_to(_SOURCE_DIRECTORY).as_posix()
            if relative.startswith(_OWN_STORE_DIRECTORY):
                continue
            for line in path.read_text().splitlines():
                if _STORE_IMPORT.match(line):
                    importing_files.append(relative)
                    break
        assert importing_files == _FILES_ALLOWED_TO_USE_STORES

    def test_store_files_never_call_a_write_command(self) -> None:
        """Checks that the files using Redis or MongoDB never call a write command."""
        offending_lines = []
        for relative in _FILES_ALLOWED_TO_USE_STORES:
            path = _SOURCE_DIRECTORY / relative
            for line_number, line in enumerate(path.read_text().splitlines()):
                if _WRITE_CALL.search(line):
                    offending_lines.append(f'{path}:{line_number + 1}: {line}')
        assert offending_lines == []

    def test_redis_reader_parses_a_json_hash_field(self) -> None:
        """Checks that a JSON hash field is parsed and a missing field is None."""
        client = _FakeRedisClient(
            {
                'last_login': {
                    'unified_broker_interface': '{"access_token": "abc"}',
                },
            }
        )
        reader = redis_reader.RedisReader(client)
        document = asyncio.run(
            reader.hash_get_json('last_login', 'unified_broker_interface')
        )
        missing = asyncio.run(reader.hash_get_json('last_login', 'zerodha'))
        assert document == {
            'access_token': 'abc',
        }
        assert missing is None

    def test_redis_reader_reports_invalid_json(self) -> None:
        """Checks that a field holding broken JSON raises ValueError.

        Raises:
            AssertionError: No error was raised.
        """
        client = _FakeRedisClient(
            {
                'last_login': {
                    'unified_broker_interface': '{broken',
                },
            }
        )
        reader = redis_reader.RedisReader(client)
        with pytest.raises(ValueError, match='last_login'):
            asyncio.run(
                reader.hash_get_json('last_login', 'unified_broker_interface')
            )

    def test_mongo_reader_returns_credentials(self) -> None:
        """Checks that the API key and secret come from UBI's settings document."""
        database = {
            'settings': _FakeCollection(
                [
                    {
                        'broker_name': 'zerodha',
                        'api_key': 'wrong',
                        'api_secret': 'wrong',
                    },
                    {
                        '_id': 1,
                        'broker_name': 'unified_broker_interface',
                        'api_key': 'key',
                        'api_secret': 'secret',
                    },
                ]
            ),
        }
        reader = mongo_reader.MongoReader(None, database)
        assert reader.api_credentials() == ('key', 'secret')

    def test_mongo_reader_refuses_incomplete_settings(self) -> None:
        """Checks that a settings document without a secret raises ValueError.

        Raises:
            AssertionError: No error was raised.
        """
        database = {
            'settings': _FakeCollection(
                [
                    {
                        'broker_name': 'unified_broker_interface',
                        'api_key': 'key',
                    },
                ]
            ),
        }
        reader = mongo_reader.MongoReader(None, database)
        with pytest.raises(ValueError, match='api_secret'):
            reader.api_credentials()

    def test_mongo_reader_returns_login_without_identifier(self) -> None:
        """Checks that the stored login is returned without MongoDB's _id."""
        database = {
            'last_login': _FakeCollection(
                [
                    {
                        '_id': 7,
                        'broker_name': 'unified_broker_interface',
                        'access_token': 'abc',
                    },
                ]
            ),
        }
        reader = mongo_reader.MongoReader(None, database)
        assert reader.stored_login() == {
            'broker_name': 'unified_broker_interface',
            'access_token': 'abc',
        }
