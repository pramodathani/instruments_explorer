"""Searches the web for a company through the Google Programmable Search JSON API.

Google does not allow its results pages to be scraped, so this fetcher uses the official API and runs only when an API key and a search engine id are set.

Typical usage example:

  result = await GoogleSearchFetcher(polite_client, key, engine_id).fetch(company)
"""

from instruments_explorer.knowledge import company_identity
from instruments_explorer.knowledge import fetched_document
from instruments_explorer.knowledge import polite_client
from instruments_explorer.knowledge.fetchers import base

SEARCH_URL = 'https://www.googleapis.com/customsearch/v1'


class GoogleSearchFetcher(base.BaseFetcher):
    """Reads Google Programmable Search results for the company.

    Attributes:
        api_key: The API key, or an empty string.
        engine_id: The search engine id, or an empty string.
    """

    def __init__(
        self,
        client: polite_client.PoliteHttpClient,
        api_key: str,
        engine_id: str,
    ):
        """Creates the fetcher.

        Args:
            client (polite_client.PoliteHttpClient): Fetches from the internet politely.
            api_key (str): The API key, or an empty string to keep the fetcher off.
            engine_id (str): The search engine id, or an empty string to keep the fetcher off.
        """
        super().__init__(
            key='google_search',
            label='Google web search',
            description='Web pages about the company from the Google Programmable Search API, with their snippets.',
            news=False,
        )
        self.api_key = api_key
        self.engine_id = engine_id
        self._client = client

    def available(self) -> tuple[bool, str]:
        """Says whether the API key and engine id are set.

        Returns:
            tuple[bool, str]: A tuple (whether it can run, and why not).
        """
        if not self.api_key or not self.engine_id:
            return (
                False,
                'Set INSTRUMENTS_EXPLORER_GOOGLE_SEARCH_API_KEY and INSTRUMENTS_EXPLORER_GOOGLE_SEARCH_ENGINE_ID to turn this on.',
            )
        return True, ''

    async def fetch(
        self,
        company: company_identity.CompanyIdentity,
    ) -> fetched_document.FetchResult:
        """Searches for the company and keeps each result's title and snippet.

        Args:
            company (company_identity.CompanyIdentity): The company.

        Returns:
            fetched_document.FetchResult: One document per result.

        Raises:
            httpx.HTTPError: Google could not be reached or refused the request.
        """
        response = await self._client.get(
            SEARCH_URL,
            params={
                'key': self.api_key,
                'cx': self.engine_id,
                'q': f'{company.short_name()} company',
                'num': 10,
            },
        )
        response.raise_for_status()
        documents = []
        for item in response.json().get('items', []):
            documents.append(
                fetched_document.FetchedDocument(
                    self.key,
                    str(item.get('title') or ''),
                    str(item.get('link') or ''),
                    None,
                    f'{item.get("title", "")}. {item.get("snippet", "")}'.strip(),
                )
            )
        return fetched_document.FetchResult(
            {},
            documents,
            f'{len(documents)} results',
        )
