"""Fetches a company's ratios, description, strengths and weaknesses, and industry classification from Screener.in.

Typical usage example:

  result = await ScreenerFetcher(polite_client).fetch(company)
"""

import bs4

from instruments_explorer.knowledge import company_identity
from instruments_explorer.knowledge import fetched_document
from instruments_explorer.knowledge import polite_client
from instruments_explorer.knowledge.fetchers import base

COMPANY_URL = 'https://www.screener.in/company/{symbol}/{view}'


class ScreenerFetcher(base.BaseFetcher):
    """Reads Screener.in's public company page."""

    def __init__(self, client: polite_client.PoliteHttpClient):
        """Creates the fetcher.

        Args:
            client (polite_client.PoliteHttpClient): Fetches from the internet politely.
        """
        super().__init__(
            key='screener',
            label='Screener.in',
            description='Key ratios, a description, key points, pros and cons, and the four-level Indian industry classification.',
            news=False,
        )
        self._client = client

    async def fetch(
        self,
        company: company_identity.CompanyIdentity,
    ) -> fetched_document.FetchResult:
        """Reads the consolidated page, or the standalone page when there is no consolidated one.

        Args:
            company (company_identity.CompanyIdentity): The company.

        Returns:
            fetched_document.FetchResult: "screener_ratios", "classification", "pros" and "cons" profile fields and one document of the page's text.

        Raises:
            polite_client.RobotsDisallowedError: Screener's robots.txt forbids the request.
            httpx.HTTPError: Screener could not be reached or refused the request.
            ValueError: Screener has no page for the symbol.
        """
        url = COMPANY_URL.format(symbol=company.symbol, view='consolidated/')
        response = await self._client.get(url)
        if response.status_code == 404:
            url = COMPANY_URL.format(symbol=company.symbol, view='')
            response = await self._client.get(url)
        if response.status_code == 404:
            raise ValueError(f'Screener.in has no page for {company.symbol}.')
        response.raise_for_status()
        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        ratios = {}
        for item in soup.select('#top-ratios li'):
            name = item.select_one('.name')
            value = item.select_one('.value')
            if name is not None and value is not None:
                ratios[name.get_text(' ', strip=True)] = value.get_text(
                    ' ', strip=True
                )
        classification = []
        for link in soup.select('#peers a[href*="/market/"]'):
            classification.append(link.get_text(strip=True))
        about = self._text(soup, '.company-profile .about')
        key_points = self._text(soup, '.company-profile .commentary')
        pros = self._items(soup, '.pros')
        cons = self._items(soup, '.cons')
        profile = {
            'screener_ratios': ratios,
            'classification': classification,
            'pros': pros,
            'cons': cons,
        }
        if about:
            profile['about'] = about
        pieces = []
        for piece in [
            about,
            key_points,
        ]:
            if piece:
                pieces.append(piece)
        if pros:
            pieces.append('Strengths: ' + ' '.join(pros))
        if cons:
            pieces.append('Weaknesses: ' + ' '.join(cons))
        documents = []
        if pieces:
            documents.append(
                fetched_document.FetchedDocument(
                    self.key,
                    f'{company.name} on Screener.in',
                    url,
                    None,
                    '\n\n'.join(pieces),
                )
            )
        return fetched_document.FetchResult(
            profile,
            documents,
            f'{len(ratios)} ratios, classified as {" › ".join(classification) or "unknown"}',
        )

    def _text(self, soup: bs4.BeautifulSoup, selector: str) -> str:
        """Reads the text of the first element matching a selector.

        Args:
            soup (bs4.BeautifulSoup): The page.
            selector (str): The CSS selector.

        Returns:
            str: The text, or an empty string.
        """
        element = soup.select_one(selector)
        if element is None:
            return ''
        return element.get_text(' ', strip=True)

    def _items(self, soup: bs4.BeautifulSoup, selector: str) -> list[str]:
        """Reads the list items inside the first element matching a selector.

        Args:
            soup (bs4.BeautifulSoup): The page.
            selector (str): The CSS selector.

        Returns:
            list[str]: The items' text.
        """
        element = soup.select_one(selector)
        if element is None:
            return []
        items = []
        for item in element.select('li'):
            text = item.get_text(' ', strip=True)
            if text:
                items.append(text)
        return items
