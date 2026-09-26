"""Fetches headlines about a company from public financial news feeds.

Paywalled publishers such as Bloomberg and The Economist contribute only what their public feeds carry, which is headlines and short summaries. Feeds are read at most once every fifteen minutes and shared between companies.

Typical usage example:

  result = await RssNewsFetcher(polite_client).fetch(company)
"""

import re
import time

import httpx

from instruments_explorer.knowledge import company_identity
from instruments_explorer.knowledge import feed_parser
from instruments_explorer.knowledge import fetched_document
from instruments_explorer.knowledge import polite_client
from instruments_explorer.knowledge.fetchers import base

FEEDS = {
    'CNBC': 'https://www.cnbc.com/id/10000664/device/rss/rss.html',
    'Investing.com': 'https://www.investing.com/rss/news_25.rss',
    'The Economist': 'https://www.economist.com/finance-and-economics/rss.xml',
    'Bloomberg': 'https://feeds.bloomberg.com/markets/news.rss',
    'Economic Times': 'https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms',
    'Mint': 'https://www.livemint.com/rss/markets',
    'Moneycontrol': 'https://www.moneycontrol.com/rss/business.xml',
}
FEED_CACHE_SECONDS = 15 * 60
MINIMUM_SYMBOL_LENGTH = 3


class RssNewsFetcher(base.BaseFetcher):
    """Reads several news feeds and keeps the headlines that mention the company."""

    def __init__(self, client: polite_client.PoliteHttpClient):
        """Creates the fetcher.

        Args:
            client (polite_client.PoliteHttpClient): Fetches from the internet politely.
        """
        super().__init__(
            key='rss_news',
            label='News feeds',
            description='Headlines mentioning the company from CNBC, Investing.com, The Economist, Bloomberg, Economic Times, Mint and Moneycontrol.',
            news=True,
        )
        self._client = client
        self._parser = feed_parser.FeedParser()
        self._cache = {}

    async def fetch(
        self,
        company: company_identity.CompanyIdentity,
    ) -> fetched_document.FetchResult:
        """Reads every feed and keeps the items mentioning the company's name, or its trading symbol when that is at least MINIMUM_SYMBOL_LENGTH letters long.

        Headlines usually say "Reliance" or "Infosys" rather than the full registered name, so the symbol catches most of them, at the cost of sometimes catching a sister company.

        Args:
            company (company_identity.CompanyIdentity): The company.

        Returns:
            fetched_document.FetchResult: One document per matching headline, and how many feeds could be read.
        """
        alternatives = [
            re.escape(company.short_name().lower()),
        ]
        if len(company.symbol) >= MINIMUM_SYMBOL_LENGTH:
            alternatives.append(re.escape(company.symbol.lower()))
        pattern = re.compile(rf'\b(?:{"|".join(alternatives)})\b')
        documents = []
        read = 0
        problems = []
        for publisher, url in FEEDS.items():
            try:
                items = await self._items(url)
            except (
                httpx.HTTPError,
                polite_client.RobotsDisallowedError,
            ) as error:
                problems.append(f'{publisher}: {type(error).__name__}')
                continue
            read += 1
            for item in items:
                haystack = f'{item.title} {item.summary}'.lower()
                if not pattern.search(haystack):
                    continue
                documents.append(
                    fetched_document.FetchedDocument(
                        self.key,
                        f'{publisher}: {item.title}',
                        item.link,
                        item.published_at,
                        f'{item.title}. {item.summary}'.strip(),
                    )
                )
        message = (
            f'{len(documents)} headlines from {read} of {len(FEEDS)} feeds'
        )
        if problems:
            message = f'{message} ({"; ".join(problems)})'
        return fetched_document.FetchResult({}, documents, message)

    async def _items(self, url: str) -> list[feed_parser.FeedItem]:
        """Reads a feed, reusing a copy fetched in the last fifteen minutes.

        Args:
            url (str): The feed's address.

        Returns:
            list[feed_parser.FeedItem]: The feed's items.

        Raises:
            polite_client.RobotsDisallowedError: The site's robots.txt forbids the feed.
            httpx.HTTPError: The feed could not be fetched.
        """
        cached = self._cache.get(url)
        if (
            cached is not None
            and time.monotonic() - cached[0] < FEED_CACHE_SECONDS
        ):
            return cached[1]
        response = await self._client.get(url)
        response.raise_for_status()
        items = self._parser.parse(response.text)
        self._cache[url] = (
            time.monotonic(),
            items,
        )
        return items
