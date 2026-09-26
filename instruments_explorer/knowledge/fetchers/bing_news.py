"""Searches Bing News for a company through Bing's public news RSS.

Typical usage example:

  result = await BingNewsFetcher(polite_client).fetch(company)
"""

from instruments_explorer.knowledge import company_identity
from instruments_explorer.knowledge import feed_parser
from instruments_explorer.knowledge import fetched_document
from instruments_explorer.knowledge import polite_client
from instruments_explorer.knowledge.fetchers import base

SEARCH_URL = 'https://www.bing.com/news/search'
MAXIMUM_ITEMS = 20


class BingNewsFetcher(base.BaseFetcher):
    """Reads Bing News results for the company's name."""

    def __init__(self, client: polite_client.PoliteHttpClient):
        """Creates the fetcher.

        Args:
            client (polite_client.PoliteHttpClient): Fetches from the internet politely.
        """
        super().__init__(
            key='bing_news',
            label='Bing News',
            description='Recent news found by searching Bing News for the company’s name.',
            news=True,
        )
        self._client = client
        self._parser = feed_parser.FeedParser()

    async def fetch(
        self,
        company: company_identity.CompanyIdentity,
    ) -> fetched_document.FetchResult:
        """Searches for the company's name in quotes.

        Args:
            company (company_identity.CompanyIdentity): The company.

        Returns:
            fetched_document.FetchResult: Up to MAXIMUM_ITEMS documents.

        Raises:
            polite_client.RobotsDisallowedError: Bing's robots.txt forbids the search.
            httpx.HTTPError: Bing could not be reached or refused the request.
        """
        response = await self._client.get(
            SEARCH_URL,
            params={
                'q': f'"{company.short_name()}"',
                'format': 'rss',
            },
        )
        response.raise_for_status()
        documents = []
        for item in self._parser.parse(response.text)[:MAXIMUM_ITEMS]:
            documents.append(
                fetched_document.FetchedDocument(
                    self.key,
                    item.title,
                    item.link,
                    item.published_at,
                    f'{item.title}. {item.summary}'.strip(),
                )
            )
        return fetched_document.FetchResult(
            {},
            documents,
            f'{len(documents)} results',
        )
