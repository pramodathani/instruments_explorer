"""Tests that instruments_explorer can only read UBI and UBI's Redis and MongoDB."""

import inspect
import re
from pathlib import Path

import pytest
from tradingmachine.ubi_stores import live_quote_reader
from tradingmachine.ubi_stores import stored_login_reader
from tradingmachine.ubi_stores import stored_login_token_source

_SOURCE_DIRECTORY = (
    Path(__file__).resolve().parent.parent / 'instruments_explorer'
)
_OWN_STORE_DIRECTORY = 'storage/'
_UBI_ACCESS_DIRECTORY = 'unified_broker_interface/'
_STORE_IMPORT = re.compile(r'^(import|from) (redis|pymongo)\b')
_TRADING_IMPORT = re.compile(
    r'^(import|from) tradingmachine\.(orders|accounts)\b'
    r'|^from tradingmachine\.assets import'
    r'|^(import|from) tradingmachine\.assets\.(?!analysis\b)'
)
_UBI_WRITE_CALL = re.compile(
    r'\.(connect|disconnect|exchange_credentials|post|put|patch|delete|'
    r'place_order|modify_order|cancel_order|flatten)\('
)
_STORE_WRITE_CALL = re.compile(
    r'\.(set|hset|hsetnx|hmset|hdel|delete|unlink|expire|sadd|srem|'
    r'lpush|rpush|xadd|xgroup_create|xack|xtrim|incr|decr|publish|'
    r'insert_one|insert_many|update_one|update_many|replace_one|'
    r'delete_one|delete_many|find_one_and_update|drop)\('
)


class TestReadOnlySources:
    """Tests that UBI is only read, through tradingmachine's read-only classes."""

    def _source_files(self) -> list[tuple[str, str]]:
        """Lists the project's Python files with their text.

        Returns:
            list[tuple[str, str]]: A tuple (path relative to the package, text) per file, sorted by path.
        """
        files = []
        for path in sorted(_SOURCE_DIRECTORY.rglob('*.py')):
            relative = path.relative_to(_SOURCE_DIRECTORY).as_posix()
            files.append(
                (
                    relative,
                    path.read_text(),
                )
            )
        return files

    def test_only_own_storage_imports_redis_or_mongodb(self) -> None:
        """Checks that nothing outside the project's own storage package imports a Redis or MongoDB client, so UBI's stores are reached only through tradingmachine."""
        importing_files = []
        for relative, text in self._source_files():
            if relative.startswith(_OWN_STORE_DIRECTORY):
                continue
            for line in text.splitlines():
                if _STORE_IMPORT.match(line):
                    importing_files.append(relative)
                    break
        assert importing_files == []

    def test_no_trading_part_of_tradingmachine_is_imported(self) -> None:
        """Checks that the order, account and instrument classes, which can place orders, are never imported."""
        offending_lines = []
        for relative, text in self._source_files():
            for line in text.splitlines():
                if _TRADING_IMPORT.match(line):
                    offending_lines.append(f'{relative}: {line}')
        assert offending_lines == []

    def test_ubi_access_never_calls_a_writing_route(self) -> None:
        """Checks that the UBI access code never connects, disconnects or sends anything but reads."""
        offending_lines = []
        for relative, text in self._source_files():
            if not relative.startswith(_UBI_ACCESS_DIRECTORY):
                continue
            for line_number, line in enumerate(text.splitlines()):
                if _UBI_WRITE_CALL.search(line):
                    offending_lines.append(
                        f'{relative}:{line_number + 1}: {line}'
                    )
        assert offending_lines == []

    @pytest.mark.parametrize(
        (
            'reader_class',
            'allowed',
        ),
        [
            (
                stored_login_reader.StoredLoginReader,
                {
                    'api_credentials',
                    'close',
                    'stored_login',
                },
            ),
            (
                live_quote_reader.LiveQuoteReader,
                {
                    'close',
                    'read',
                },
            ),
        ],
    )
    def test_tradingmachine_store_readers_only_read(
        self,
        reader_class: type,
        allowed: set[str],
    ) -> None:
        """Checks that tradingmachine's readers of UBI's stores offer nothing beyond their reads.

        Args:
            reader_class (type): The reader class.
            allowed (set[str]): The public method names it may have.
        """
        public = set()
        for name, _ in inspect.getmembers(reader_class, inspect.isfunction):
            if not name.startswith('_'):
                public.add(name)
        assert public == allowed

    @pytest.mark.parametrize(
        'module',
        [
            stored_login_reader,
            live_quote_reader,
            stored_login_token_source,
        ],
    )
    def test_tradingmachine_store_modules_never_write(
        self,
        module: object,
    ) -> None:
        """Checks that tradingmachine's modules touching UBI's stores contain no Redis or MongoDB write command.

        Args:
            module (object): The tradingmachine module.
        """
        offending_lines = []
        for line in inspect.getsource(module).splitlines():
            if _STORE_WRITE_CALL.search(line):
                offending_lines.append(line)
        assert offending_lines == []
