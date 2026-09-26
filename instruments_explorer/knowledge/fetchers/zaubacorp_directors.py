"""Reads a company's current directors and key managerial personnel from Zaubacorp, which republishes the Ministry of Corporate Affairs company registry.

The registry lists every director, including the independent and non-executive directors that Yahoo leaves out, with each one's DIN (director identification number), designation and appointment date. Zaubacorp finds a company by name; the result whose registration number (CIN) starts with "L", meaning a listed company, and whose name matches is chosen. Both pages are allowed by Zaubacorp's robots.txt and fetched through the polite client.

Typical usage example:

  result = await ZaubacorpDirectorsFetcher(polite_client).fetch(company)
"""

import re
from typing import Any

import bs4

from instruments_explorer.knowledge import company_identity
from instruments_explorer.knowledge import fetched_document
from instruments_explorer.knowledge import polite_client
from instruments_explorer.knowledge.fetchers import base

SEARCH_URL = 'https://www.zaubacorp.com/companysearchresults/{slug}'
CIN_PATTERN = re.compile(r'[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}')
_NAME_NOISE = re.compile(r'\b(limited|ltd|the|and|of|india|private|pvt)\b')


class ZaubacorpDirectorsFetcher(base.BaseFetcher):
    """Reads the board of directors and key managerial personnel from the company registry."""

    def __init__(self, client: polite_client.PoliteHttpClient):
        """Creates the fetcher.

        Args:
            client (polite_client.PoliteHttpClient): Fetches pages politely.
        """
        super().__init__(
            key='zaubacorp',
            label='Board (company registry)',
            description='The full board of directors, including independent directors, and key managerial personnel from the Ministry of Corporate Affairs registry through Zaubacorp, with appointment dates.',
            news=False,
        )
        self._client = client

    async def fetch(
        self,
        company: company_identity.CompanyIdentity,
    ) -> fetched_document.FetchResult:
        """Finds the company and reads its current directors.

        Args:
            company (company_identity.CompanyIdentity): The company.

        Returns:
            fetched_document.FetchResult: The registration number under "cin" and the people under "key_people.zaubacorp".

        Raises:
            ValueError: No listed company with that name was found, or its page has no directors table.
            polite_client.RobotsDisallowedError: robots.txt forbids a page.
            httpx.HTTPError: Zaubacorp could not be reached.
        """
        slug = re.sub(r'[^A-Z0-9]+', '-', company.name.upper()).strip('-')
        response = await self._client.get(SEARCH_URL.format(slug=slug))
        response.raise_for_status()
        page_url, cin = self.choose_result(response.text, company.name)
        page = await self._client.get(page_url)
        page.raise_for_status()
        people = self.parse_directors(page.text)
        if not people:
            raise ValueError(
                f'Zaubacorp shows no current directors for {company.name}.'
            )
        return fetched_document.FetchResult(
            {
                'cin': cin,
                'key_people.zaubacorp': people,
            },
            [],
            f'{len(people)} directors and officers, CIN {cin}',
        )

    def choose_result(self, html: str, name: str) -> tuple[str, str]:
        """Picks the listed company whose name matches from a search results page.

        Args:
            html (str): The search results page.
            name (str): The company's name, such as "Reliance Industries Limited".

        Returns:
            tuple[str, str]: A tuple (the company page's address, its CIN).

        Raises:
            ValueError: No listed company with a matching name is on the page.
        """
        soup = bs4.BeautifulSoup(html, 'html.parser')
        wanted = self._name_key(name)
        best = None
        for link in soup.select('.companies-list h2 a[href]'):
            href = link['href']
            found = CIN_PATTERN.search(href)
            if found is None or not found.group().startswith('L'):
                continue
            if self._name_key(link.get_text(' ', strip=True)) == wanted:
                return href, found.group()
            if best is None:
                best = (href, found.group(), link.get_text(' ', strip=True))
        if best is not None and self._close(best[2], name):
            return best[0], best[1]
        raise ValueError(f'Zaubacorp lists no listed company named {name!r}.')

    def parse_directors(self, html: str) -> list[dict[str, Any]]:
        """Reads the "Current Directors & Key Managerial Personnel" table of a company page.

        Args:
            html (str): The company page.

        Returns:
            list[dict[str, Any]]: One {"name", "role", "din", "appointed_on"} per person.
        """
        soup = bs4.BeautifulSoup(html, 'html.parser')
        heading = soup.find(string=re.compile(r'Current Directors'))
        if heading is None:
            return []
        table = heading.find_next('table')
        if table is None:
            return []
        people = []
        for row in table.find_all('tr'):
            cells = []
            for cell in row.find_all('td'):
                cells.append(cell.get_text(' ', strip=True))
            if len(cells) < 3 or not cells[1]:
                continue
            people.append(
                {
                    'name': ' '.join(cells[1].split()),
                    'role': cells[2],
                    'din': cells[0] or None,
                    'appointed_on': cells[3]
                    if len(cells) > 3 and cells[3]
                    else None,
                }
            )
        return people

    def _name_key(self, name: str) -> str:
        """Normalises a company name for comparison, ignoring words such as "Limited".

        Args:
            name (str): The name.

        Returns:
            str: The name's remaining words, lower case, joined by spaces.
        """
        words = re.sub(r'[^a-z0-9 ]', ' ', name.lower())
        return ' '.join(_NAME_NOISE.sub(' ', words).split())

    def _close(self, found: str, wanted: str) -> bool:
        """Says whether a found name shares every significant word with the wanted one.

        Args:
            found (str): The name on the results page.
            wanted (str): The company's name.

        Returns:
            bool: True when every word of the wanted name appears in the found name.
        """
        found_words = set(self._name_key(found).split())
        wanted_words = self._name_key(wanted).split()
        return bool(wanted_words) and all(
            word in found_words for word in wanted_words
        )
