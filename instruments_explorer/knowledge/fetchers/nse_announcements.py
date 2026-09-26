"""Fetches a company's latest corporate announcements from NSE.

Typical usage example:

  result = await NseAnnouncementsFetcher(polite_client).fetch(company)
"""

import datetime

from instruments_explorer.knowledge import company_identity
from instruments_explorer.knowledge import fetched_document
from instruments_explorer.knowledge import polite_client
from instruments_explorer.knowledge.fetchers import base

ANNOUNCEMENTS_URL = 'https://www.nseindia.com/api/corporate-announcements'
MAXIMUM_ANNOUNCEMENTS = 30
_INDIA = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


class NseAnnouncementsFetcher(base.BaseFetcher):
    """Reads NSE's corporate announcements, such as results, dividends and board meetings."""

    def __init__(self, client: polite_client.PoliteHttpClient):
        """Creates the fetcher.

        Args:
            client (polite_client.PoliteHttpClient): Fetches from the internet politely.
        """
        super().__init__(
            key='nse_announcements',
            label='NSE announcements',
            description='The latest corporate announcements filed on NSE: results, dividends, board meetings and the like.',
            news=True,
        )
        self._client = client

    async def fetch(
        self,
        company: company_identity.CompanyIdentity,
    ) -> fetched_document.FetchResult:
        """Reads the company's latest announcements.

        Args:
            company (company_identity.CompanyIdentity): The company.

        Returns:
            fetched_document.FetchResult: Up to MAXIMUM_ANNOUNCEMENTS documents.

        Raises:
            polite_client.RobotsDisallowedError: NSE's robots.txt forbids the request.
            httpx.HTTPError: NSE could not be reached or refused the request.
            ValueError: NSE's answer is not the expected JSON.
        """
        if company.exchange != 'nse':
            return fetched_document.FetchResult(
                {},
                [],
                'Only NSE-listed companies have NSE announcements.',
            )
        response = await self._client.get(
            ANNOUNCEMENTS_URL,
            params={
                'index': 'equities',
                'symbol': company.symbol,
            },
            headers={
                'Accept': 'application/json',
                'Referer': 'https://www.nseindia.com/companies-listing/corporate-filings-announcements',
            },
        )
        response.raise_for_status()
        items = response.json()
        if not isinstance(items, list):
            raise ValueError(
                'NSE answered announcements with something other than a list.'
            )
        documents = []
        for item in items[:MAXIMUM_ANNOUNCEMENTS]:
            subject = str(item.get('desc') or 'Announcement')
            detail = str(item.get('attchmntText') or '')
            documents.append(
                fetched_document.FetchedDocument(
                    self.key,
                    subject,
                    str(item.get('attchmntFile') or ''),
                    self._date(item.get('an_dt')),
                    f'{subject}. {detail}'.strip(),
                )
            )
        return fetched_document.FetchResult(
            {},
            documents,
            f'{len(documents)} announcements',
        )

    def _date(self, text: object) -> float | None:
        """Reads NSE's announcement time, such as "25-Sep-2026 22:49:03", in India time.

        Args:
            text (object): The time text.

        Returns:
            float | None: Epoch seconds, or None when it is not a time.
        """
        try:
            moment = datetime.datetime.strptime(str(text), '%d-%b-%Y %H:%M:%S')  # noqa: DTZ007
        except ValueError:
            return None
        return moment.replace(tzinfo=_INDIA).timestamp()
