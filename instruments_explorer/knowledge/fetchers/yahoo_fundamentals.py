"""Fetches a company's profile and fundamentals from Yahoo Finance through the yfinance library.

yfinance makes its own requests to Yahoo's data servers, so this fetcher does not go through the polite client; it asks for one company at a time and only when a job runs.

Typical usage example:

  result = await YahooFundamentalsFetcher().fetch(company)
"""

import asyncio
from typing import Any

import yfinance

from instruments_explorer.knowledge import company_identity
from instruments_explorer.knowledge import fetched_document
from instruments_explorer.knowledge.fetchers import base

_SUFFIXES = {
    'nse': '.NS',
    'bse': '.BO',
}
_PROFILE_FIELDS = {
    'longName': 'yahoo_name',
    'sector': 'sector',
    'industry': 'industry',
    'website': 'website',
    'fullTimeEmployees': 'employees',
    'city': 'city',
    'country': 'country',
}
_FUNDAMENTAL_FIELDS = [
    'marketCap',
    'trailingPE',
    'forwardPE',
    'priceToBook',
    'bookValue',
    'dividendYield',
    'beta',
    'debtToEquity',
    'returnOnEquity',
    'returnOnAssets',
    'profitMargins',
    'operatingMargins',
    'revenueGrowth',
    'earningsGrowth',
    'totalRevenue',
    'ebitda',
    'fiftyTwoWeekHigh',
    'fiftyTwoWeekLow',
]


class YahooFundamentalsFetcher(base.BaseFetcher):
    """Reads sector, industry, business summary and fundamentals from Yahoo Finance."""

    def __init__(self):
        """Creates the fetcher."""
        super().__init__(
            key='yahoo',
            label='Yahoo Finance',
            description='Sector, industry, website, employees, a business summary and fundamentals such as P/E, margins and growth.',
            news=False,
        )

    async def fetch(
        self,
        company: company_identity.CompanyIdentity,
    ) -> fetched_document.FetchResult:
        """Reads the company's profile and fundamentals.

        Args:
            company (company_identity.CompanyIdentity): The company.

        Returns:
            fetched_document.FetchResult: Profile fields, fundamentals under "fundamentals", and the business summary as a document.

        Raises:
            ValueError: The exchange has no Yahoo suffix, or Yahoo knows nothing about the symbol.
        """
        suffix = _SUFFIXES.get(company.exchange)
        if suffix is None:
            raise ValueError(
                f'Yahoo has no symbols for exchange {company.exchange!r}.'
            )
        ticker_symbol = f'{company.symbol}{suffix}'
        info = await asyncio.to_thread(self._read_info, ticker_symbol)
        if not info or not info.get('longName'):
            raise ValueError(
                f'Yahoo Finance knows nothing about {ticker_symbol}.'
            )
        profile = {}
        for yahoo_field, our_field in _PROFILE_FIELDS.items():
            if info.get(yahoo_field) is not None:
                profile[our_field] = info[yahoo_field]
        fundamentals = {}
        for field in _FUNDAMENTAL_FIELDS:
            value = info.get(field)
            if isinstance(value, (int, float)):
                fundamentals[field] = value
        profile['fundamentals'] = fundamentals
        documents = []
        summary = info.get('longBusinessSummary')
        if summary:
            documents.append(
                fetched_document.FetchedDocument(
                    self.key,
                    f'{info["longName"]}: business summary',
                    f'https://finance.yahoo.com/quote/{ticker_symbol}/profile',
                    None,
                    summary,
                )
            )
        return fetched_document.FetchResult(
            profile,
            documents,
            f'{len(fundamentals)} fundamentals, sector {profile.get("sector", "unknown")}',
        )

    def _read_info(self, ticker_symbol: str) -> dict[str, Any]:
        """Asks yfinance for a symbol's information; runs in a worker thread.

        Args:
            ticker_symbol (str): Yahoo's symbol, such as "RELIANCE.NS".

        Returns:
            dict[str, Any]: The information yfinance returned.
        """
        return dict(yfinance.Ticker(ticker_symbol).info or {})
