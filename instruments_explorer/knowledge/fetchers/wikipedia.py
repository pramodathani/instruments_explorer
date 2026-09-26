"""Fetches a company's Wikipedia summary.

Wikipedia's robot policy asks automated clients to name themselves and give contact details in the user agent, so this fetcher runs only when INSTRUMENTS_EXPLORER_KNOWLEDGE_CONTACT is set.

Typical usage example:

  result = await WikipediaFetcher(polite_client, 'you@example.com').fetch(company)
"""

import urllib.parse

from instruments_explorer.knowledge import company_identity
from instruments_explorer.knowledge import fetched_document
from instruments_explorer.knowledge import polite_client
from instruments_explorer.knowledge.fetchers import base

SEARCH_URL = 'https://en.wikipedia.org/w/api.php'
SUMMARY_URL = 'https://en.wikipedia.org/api/rest_v1/page/summary/{title}'


class WikipediaFetcher(base.BaseFetcher):
    """Finds the company's English Wikipedia article and reads its summary.

    Attributes:
        contact: The contact details sent in the user agent, or an empty string.
    """

    def __init__(self, client: polite_client.PoliteHttpClient, contact: str):
        """Creates the fetcher.

        Args:
            client (polite_client.PoliteHttpClient): Fetches from the internet politely.
            contact (str): Contact details for the user agent, or an empty string to keep the fetcher off.
        """
        super().__init__(
            key='wikipedia',
            label='Wikipedia',
            description='A plain-language overview of the company from its English Wikipedia article.',
            news=False,
        )
        self.contact = contact
        self._client = client

    def available(self) -> tuple[bool, str]:
        """Says whether contact details are set, as Wikipedia's robot policy requires.

        Returns:
            tuple[bool, str]: A tuple (whether it can run, and why not).
        """
        if not self.contact:
            return (
                False,
                'Wikipedia asks automated clients for contact details; set INSTRUMENTS_EXPLORER_KNOWLEDGE_CONTACT to turn this on.',
            )
        return True, ''

    async def fetch(
        self,
        company: company_identity.CompanyIdentity,
    ) -> fetched_document.FetchResult:
        """Searches for the company's article and reads its summary.

        Args:
            company (company_identity.CompanyIdentity): The company.

        Returns:
            fetched_document.FetchResult: The summary as a document and "wikipedia_title" in the profile.

        Raises:
            polite_client.RobotsDisallowedError: Wikipedia's robots.txt forbids the request.
            httpx.HTTPError: Wikipedia could not be reached or refused the request.
            ValueError: No article was found.
        """
        headers = {
            'User-Agent': f'instruments_explorer/0.1 ({self.contact})',
        }
        search = await self._client.get(
            SEARCH_URL,
            params={
                'action': 'query',
                'list': 'search',
                'srsearch': f'{company.short_name()} company India',
                'srlimit': 1,
                'format': 'json',
            },
            headers=headers,
        )
        search.raise_for_status()
        hits = search.json().get('query', {}).get('search', [])
        if not hits:
            raise ValueError(f'Wikipedia has no article about {company.name}.')
        title = hits[0]['title']
        summary = await self._client.get(
            SUMMARY_URL.format(
                title=urllib.parse.quote(title.replace(' ', '_'))
            ),
            headers=headers,
        )
        summary.raise_for_status()
        body = summary.json()
        extract = body.get('extract') or ''
        page = body.get('content_urls', {}).get('desktop', {}).get('page', '')
        documents = []
        if extract:
            documents.append(
                fetched_document.FetchedDocument(
                    self.key,
                    f'Wikipedia: {title}',
                    page,
                    None,
                    extract,
                )
            )
        return fetched_document.FetchResult(
            {
                'wikipedia_title': title,
            },
            documents,
            f'Article "{title}"',
        )
