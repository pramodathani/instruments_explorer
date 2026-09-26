"""Turns what a user types into an SQLite full-text search expression.

Typical usage example:

  query = SearchQueryParser().parse('Nifty sep 23500 ce')
  query.expression  # '"nifty"* "sep"* "23500"* "ce"*'
"""

import re

_WORD = re.compile(r'[0-9a-z]+')
_MAXIMUM_WORDS = 8


class SearchQuery:
    """A parsed search.

    Attributes:
        words: The lower-case words typed, at most eight.
        expression: The FTS5 expression matching instruments that have a word starting with each typed word.
        first_word: The first word, used to put exact name matches first.
    """

    def __init__(self, words: list[str]):
        """Creates the query from its words.

        Args:
            words (list[str]): The lower-case words, at least one.
        """
        self.words = words
        quoted = []
        for word in words:
            quoted.append(f'"{word}"*')
        self.expression = ' '.join(quoted)
        self.first_word = words[0]


class SearchQueryParser:
    """Splits typed text into search words."""

    def parse(self, text: str) -> SearchQuery | None:
        """Parses typed text.

        Only letters and digits count, so punctuation can never break the full-text expression.

        Args:
            text (str): The text typed into the search box.

        Returns:
            SearchQuery | None: The query, or None when the text has no letters or digits.
        """
        words = _WORD.findall(text.lower())[:_MAXIMUM_WORDS]
        if not words:
            return None
        return SearchQuery(words)
