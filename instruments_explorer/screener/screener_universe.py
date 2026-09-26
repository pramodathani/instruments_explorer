"""The groups of stocks the screener covers.

Typical usage example:

  members = await ScreenerUniverse(maintainer, companies).members('total_market')
"""

import asyncio
from typing import Any

from instruments_explorer.instruments import instrument_index_maintainer
from instruments_explorer.storage import company_repository

UNIVERSES = {
    'total_market': 'Nifty Total Market (about 750 stocks)',
    'all_nse': 'All NSE equities (about 2,500 stocks)',
}


class ScreenerUniverse:
    """Lists the stocks of a universe with their instrument ids, names and sectors."""

    def __init__(
        self,
        maintainer: instrument_index_maintainer.InstrumentIndexMaintainer,
        companies: company_repository.CompanyRepository,
    ):
        """Creates the universe.

        Args:
            maintainer (instrument_index_maintainer.InstrumentIndexMaintainer): Holds the instrument index, which maps symbols to instrument ids.
            companies (company_repository.CompanyRepository): Holds the companies with their index membership and sectors.
        """
        self._maintainer = maintainer
        self._companies = companies

    def describe(self) -> list[dict[str, str]]:
        """Describes the universes for the browser.

        Returns:
            list[dict[str, str]]: One {"key", "label"} per universe.
        """
        universes = []
        for key, label in UNIVERSES.items():
            universes.append(
                {
                    'key': key,
                    'label': label,
                }
            )
        return universes

    async def members(self, universe: str) -> list[dict[str, Any]]:
        """Lists a universe's stocks that the instrument index knows.

        Args:
            universe (str): One of UNIVERSES.

        Returns:
            list[dict[str, Any]]: One {"instrument_id", "symbol", "name", "sector"} per stock, by symbol; "sector" is "Unclassified" when no source reports one.

        Raises:
            ValueError: The universe is unknown.
            LookupError: The instrument index is not ready.
        """
        if universe not in UNIVERSES:
            raise ValueError(f'Unknown screener universe: {universe!r}')
        index = self._maintainer.current_index
        if index is None:
            raise LookupError('The instrument index is not ready yet.')
        shares = await asyncio.to_thread(index.share_ids_by_symbol, 'nse')
        companies = await self._companies.screener_members(
            only_total_market=universe == 'total_market',
        )
        members = []
        for company in companies:
            instrument_id = shares.get(company['symbol'])
            if instrument_id is None:
                continue
            members.append(
                {
                    'instrument_id': instrument_id,
                    'symbol': company['symbol'],
                    'name': company.get('name')
                    or company.get('index_name')
                    or company['symbol'],
                    'sector': self._companies.sector(company) or 'Unclassified',
                }
            )
        members.sort(key=lambda member: member['symbol'])
        return members
