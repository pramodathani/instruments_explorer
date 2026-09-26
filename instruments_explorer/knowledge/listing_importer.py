"""Imports NSE's list of every listed equity, which gives each company its full name and ISIN, and the Nifty Total Market constituents, which give about 750 of them an industry.

The equity list is one CSV file of about 2,600 rows published by NSE. It seeds the companies collection, and the names it brings make companies findable by name in the instrument search. The constituent list's industries are the sectors of the screener's heatmap and of the Explore sector filter.

Typical usage example:

  importer = ListingImporter(polite_client, companies, clock)
  count = await importer.import_nse()
"""

import csv
import datetime
import io
from typing import Any

from instruments_explorer.knowledge import polite_client
from instruments_explorer.storage import company_repository
from instruments_explorer.utilities import clock

NSE_EQUITY_LIST_URL = (
    'https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv'
)
TOTAL_MARKET_LIST_URL = 'https://nsearchives.nseindia.com/content/indices/ind_niftytotalmarket_list.csv'


class ListingImporter:
    """Reads NSE's equity list and stores every company in it."""

    def __init__(
        self,
        client: polite_client.PoliteHttpClient,
        companies: company_repository.CompanyRepository,
        time_source: clock.SystemClock,
    ):
        """Creates the importer.

        Args:
            client (polite_client.PoliteHttpClient): Fetches from the internet politely.
            companies (company_repository.CompanyRepository): Stores the companies.
            time_source (clock.SystemClock): The source of the current time.
        """
        self._client = client
        self._companies = companies
        self._time_source = time_source

    async def import_nse(self) -> int:
        """Downloads NSE's equity list and stores every company in it.

        Returns:
            int: The number of companies stored.

        Raises:
            polite_client.RobotsDisallowedError: NSE's robots.txt forbids the download.
            httpx.HTTPError: NSE could not be reached or refused the request.
            ValueError: The file has no rows with a symbol, name and ISIN.
        """
        response = await self._client.get(NSE_EQUITY_LIST_URL)
        response.raise_for_status()
        listings = self.parse(response.text)
        if not listings:
            raise ValueError(
                'NSE equity list has no rows with a symbol, name and ISIN.'
            )
        return await self._companies.upsert_listings(
            listings,
            self._time_source.now(),
        )

    async def import_sectors(self) -> int:
        """Downloads the Nifty Total Market index's constituents, which give about 750 companies an industry, and stores them.

        Returns:
            int: The number of companies given an industry.

        Raises:
            polite_client.RobotsDisallowedError: NSE's robots.txt forbids the download.
            httpx.HTTPError: NSE could not be reached or refused the request.
            ValueError: The file has no rows with an ISIN and an industry.
        """
        response = await self._client.get(TOTAL_MARKET_LIST_URL)
        response.raise_for_status()
        constituents = self.parse_constituents(response.text)
        if not constituents:
            raise ValueError(
                'The Nifty Total Market list has no rows with an ISIN and an industry.'
            )
        return await self._companies.set_index_industries(
            constituents,
            self._time_source.now(),
        )

    def parse_constituents(self, text: str) -> list[dict[str, str]]:
        """Reads an index constituent CSV with "Company Name", "Industry", "Symbol", "Series" and "ISIN Code".

        Args:
            text (str): The CSV text.

        Returns:
            list[dict[str, str]]: One {"company_key", "name", "industry", "symbol", "isin"} per row with an ISIN and an industry.
        """
        constituents = []
        for row in csv.DictReader(io.StringIO(text)):
            cleaned = {}
            for key, value in row.items():
                if key is not None:
                    cleaned[key.strip()] = (value or '').strip()
            isin = cleaned.get('ISIN Code')
            industry = cleaned.get('Industry')
            symbol = cleaned.get('Symbol')
            if not isin or not industry or not symbol:
                continue
            constituents.append(
                {
                    'company_key': isin,
                    'name': cleaned.get('Company Name') or symbol,
                    'industry': industry,
                    'symbol': symbol,
                    'isin': isin,
                }
            )
        return constituents

    def parse(self, text: str) -> list[dict[str, Any]]:
        """Reads the CSV into company listings.

        NSE's headers carry stray spaces, such as " ISIN NUMBER", so they are stripped before use.

        Args:
            text (str): The CSV text.

        Returns:
            list[dict[str, Any]]: One listing per row with a symbol, name and ISIN, keyed by ISIN.
        """
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            return []
        headers = []
        for header in rows[0]:
            headers.append(header.strip().upper())
        listings = []
        for row in rows[1:]:
            values = {}
            for position, header in enumerate(headers):
                if position < len(row):
                    values[header] = row[position].strip()
            symbol = values.get('SYMBOL')
            name = values.get('NAME OF COMPANY')
            isin = values.get('ISIN NUMBER')
            if not symbol or not name or not isin:
                continue
            listings.append(
                {
                    'company_key': isin,
                    'name': name,
                    'isin': isin,
                    'exchange': 'nse',
                    'symbol': symbol,
                    'series': values.get('SERIES'),
                    'listed_on': self._date(values.get('DATE OF LISTING')),
                    'face_value': self._number(values.get('FACE VALUE')),
                }
            )
        return listings

    def _date(self, text: str | None) -> str | None:
        """Reads NSE's listing date, such as "29-NOV-1995".

        Args:
            text (str | None): The date text.

        Returns:
            str | None: The date as "YYYY-MM-DD", or None.
        """
        if not text:
            return None
        try:
            moment = datetime.datetime.strptime(text.title(), '%d-%b-%Y')  # noqa: DTZ007
        except ValueError:
            return None
        return moment.date().isoformat()

    def _number(self, text: str | None) -> float | None:
        """Reads a number.

        Args:
            text (str | None): The number text.

        Returns:
            float | None: The number, or None.
        """
        try:
            return float(text) if text else None
        except ValueError:
            return None
