"""Tests for parsing a JSON array that arrives in pieces."""

import json

import pytest

from instruments_explorer.unified_broker_interface import (
    json_array_stream_parser,
)

_VALUES = [
    {
        'instrument_id': 'a',
        'symbol': 'INFY',
        'strike_price': None,
    },
    {
        'instrument_id': 'b',
        'symbol': 'NIFTY [50], {index}',
        'strike_price': 23500.0,
    },
    {
        'instrument_id': 'c',
        'symbol': 'Ünïcode ₹',
        'strike_price': 85.75,
    },
    12345,
    'plain text',
]


class TestJsonArrayStreamParser:
    """Tests for JsonArrayStreamParser."""

    def test_every_split_point_gives_the_same_values(self) -> None:
        """Checks that splitting the text anywhere, even inside a value, gives every value once in order."""
        text = json.dumps(_VALUES, separators=(',', ':'), ensure_ascii=False)
        for split_at in range(len(text) + 1):
            parser = json_array_stream_parser.JsonArrayStreamParser()
            values = parser.feed(text[:split_at])
            values.extend(parser.feed(text[split_at:]))
            parser.finish()
            assert values == _VALUES, split_at

    def test_one_character_at_a_time(self) -> None:
        """Checks that feeding one character at a time works and counts the values."""
        text = json.dumps(_VALUES, indent=2)
        parser = json_array_stream_parser.JsonArrayStreamParser()
        values = []
        for character in text:
            values.extend(parser.feed(character))
        parser.finish()
        assert values == _VALUES
        assert parser.item_count == len(_VALUES)

    def test_empty_array(self) -> None:
        """Checks that an empty array gives no values and finishes cleanly."""
        parser = json_array_stream_parser.JsonArrayStreamParser()
        assert parser.feed('[ ]') == []
        parser.finish()

    def test_truncated_array_is_reported(self) -> None:
        """Checks that a stream cut off before the closing bracket fails at finish.

        Raises:
            AssertionError: No error was raised.
        """
        text = json.dumps(_VALUES)
        parser = json_array_stream_parser.JsonArrayStreamParser()
        parser.feed(text[: len(text) // 2])
        with pytest.raises(ValueError, match='ended early'):
            parser.finish()

    def test_text_that_is_not_an_array_is_refused(self) -> None:
        """Checks that a JSON object instead of an array is refused.

        Raises:
            AssertionError: No error was raised.
        """
        parser = json_array_stream_parser.JsonArrayStreamParser()
        with pytest.raises(ValueError, match='does not start'):
            parser.feed('{"error": "x"}')

    def test_text_after_the_array_is_refused(self) -> None:
        """Checks that text after the closing bracket is refused.

        Raises:
            AssertionError: No error was raised.
        """
        parser = json_array_stream_parser.JsonArrayStreamParser()
        with pytest.raises(ValueError, match='after the end'):
            parser.feed('[1, 2] 3')
