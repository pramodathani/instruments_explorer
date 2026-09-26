"""Reads the objects of a JSON array as its text arrives in pieces.

UBI streams long answers, such as its instrument master, as one compact JSON array written in chunks of about 64 KB, with no line breaks between objects. The parser returns each object as soon as its text is complete, so the whole array is never held in memory.

Typical usage example:

  parser = JsonArrayStreamParser()
  async for text in response.aiter_text():
      for item in parser.feed(text):
          ...
  parser.finish()
"""

import json
from typing import Any


class JsonArrayStreamParser:
    """Parses one top-level JSON array of values fed as consecutive text pieces.

    Attributes:
        item_count: How many values have been returned so far.
    """

    def __init__(self):
        """Creates a parser waiting for the opening bracket."""
        self.item_count = 0
        self._decoder = json.JSONDecoder()
        self._buffer = ''
        self._started = False
        self._finished = False

    def feed(self, text: str) -> list[Any]:
        """Adds the next piece of text and returns the values it completes.

        Args:
            text (str): The next piece of the array's text.

        Returns:
            list[Any]: The values completed by this piece, in order.

        Raises:
            ValueError: The text is not a JSON array, or has text after the closing bracket.
        """
        self._buffer += text
        values = []
        position = 0
        length = len(self._buffer)
        while True:
            position = self._skip_whitespace(position)
            if position >= length:
                break
            character = self._buffer[position]
            if not self._started:
                if character != '[':
                    raise ValueError(
                        'The stream does not start with a JSON array.'
                    )
                self._started = True
                position += 1
                continue
            if self._finished:
                raise ValueError(
                    'The stream has text after the end of the JSON array.'
                )
            if character == ']':
                self._finished = True
                position += 1
                continue
            if character == ',':
                position += 1
                continue
            try:
                value, end = self._decoder.raw_decode(self._buffer, position)
            except json.JSONDecodeError:
                break
            if end >= length:
                break
            values.append(value)
            position = end
        self._buffer = self._buffer[position:]
        self.item_count += len(values)
        return values

    def finish(self) -> None:
        """Checks that the whole array arrived.

        A value is only returned once the character after it has arrived, so a complete array leaves nothing buffered once its closing bracket is fed.

        Raises:
            ValueError: The array never started, never ended, or has text left after its end.
        """
        leftover = self._buffer.strip()
        if not self._started or not self._finished or leftover:
            raise ValueError(
                f'The JSON array ended early, after {self.item_count} values.'
            )

    def _skip_whitespace(self, position: int) -> int:
        """Moves past whitespace in the buffer.

        Args:
            position (int): Where to start.

        Returns:
            int: The position of the next character that is not whitespace.
        """
        length = len(self._buffer)
        while position < length and self._buffer[position] in ' \t\r\n':
            position += 1
        return position
