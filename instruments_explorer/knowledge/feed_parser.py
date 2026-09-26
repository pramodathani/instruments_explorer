"""Reads RSS 2.0 and Atom news feeds.

Typical usage example:

  items = FeedParser().parse(xml_text)
"""

import email.utils
import xml.etree.ElementTree

from instruments_explorer.knowledge import text_extractor

_ATOM = '{http://www.w3.org/2005/Atom}'


class FeedItem:
    """One headline from a feed.

    Attributes:
        title: The headline.
        link: The article's address.
        summary: The feed's summary of the article, as plain text.
        published_at: When it was published, in epoch seconds, or None.
    """

    def __init__(
        self,
        title: str,
        link: str,
        summary: str,
        published_at: float | None,
    ):
        """Creates the item.

        Args:
            title (str): The headline.
            link (str): The article's address.
            summary (str): The summary as plain text.
            published_at (float | None): When it was published, in epoch seconds, or None.
        """
        self.title = title
        self.link = link
        self.summary = summary
        self.published_at = published_at


class FeedParser:
    """Turns a feed's XML into items, whichever of the two common formats it uses."""

    def __init__(self):
        """Creates the parser."""
        self._extractor = text_extractor.TextExtractor()

    def parse(self, xml_text: str) -> list[FeedItem]:
        """Reads every item of a feed.

        Args:
            xml_text (str): The feed's XML.

        Returns:
            list[FeedItem]: The items in feed order; empty when the XML cannot be read.
        """
        try:
            root = xml.etree.ElementTree.fromstring(xml_text.strip())
        except xml.etree.ElementTree.ParseError:
            return []
        items = []
        for element in root.iter('item'):
            items.append(
                FeedItem(
                    self._text(element, 'title'),
                    self._text(element, 'link'),
                    self._plain(self._text(element, 'description')),
                    self._rss_date(self._text(element, 'pubDate')),
                )
            )
        for element in root.iter(f'{_ATOM}entry'):
            link = element.find(f'{_ATOM}link')
            items.append(
                FeedItem(
                    self._text(element, f'{_ATOM}title'),
                    link.get('href', '') if link is not None else '',
                    self._plain(self._text(element, f'{_ATOM}summary')),
                    None,
                )
            )
        return items

    def _text(self, element: xml.etree.ElementTree.Element, tag: str) -> str:
        """Reads a child element's text.

        Args:
            element (xml.etree.ElementTree.Element): The parent.
            tag (str): The child's tag.

        Returns:
            str: The stripped text, or an empty string when the child is missing.
        """
        child = element.find(tag)
        if child is None or child.text is None:
            return ''
        return child.text.strip()

    def _plain(self, markup: str) -> str:
        """Removes HTML from a summary.

        Args:
            markup (str): The summary, which may hold HTML.

        Returns:
            str: Plain text.
        """
        if '<' not in markup:
            return markup
        return self._extractor.html(markup)

    def _rss_date(self, text: str) -> float | None:
        """Reads an RSS date such as "Fri, 25 Sep 2026 10:00:00 GMT".

        Args:
            text (str): The date text.

        Returns:
            float | None: Epoch seconds, or None when the text is not a date.
        """
        if not text:
            return None
        try:
            return email.utils.parsedate_to_datetime(text).timestamp()
        except TypeError, ValueError:
            return None
