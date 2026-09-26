"""Works out which company an instrument belongs to.

A share is its company; a future or option on a share belongs to the company behind it. Indices, commodities, currencies and bonds are not companies, so they are refused.

Typical usage example:

  company = await CompanyResolver(maintainer, client, companies).resolve(instrument_id)
"""

import asyncio

from instruments_explorer.instruments import instrument_index_maintainer
from instruments_explorer.knowledge import company_identity
from instruments_explorer.storage import company_repository
from instruments_explorer.unified_broker_interface import exceptions
from instruments_explorer.unified_broker_interface import rest_client

_COMPANY_SEGMENTS = [
    'equities',
    'equity_futures',
    'equity_options',
    'exchange_traded_funds',
    'investment_trusts',
    'uncategorised',
]


class NotACompanyError(ValueError):
    """The instrument is not a company's share or a derivative on one."""


class CompanyResolver:
    """Finds a company's identity from an instrument id."""

    def __init__(
        self,
        maintainer: instrument_index_maintainer.InstrumentIndexMaintainer,
        client: rest_client.UnifiedBrokerInterfaceClient,
        companies: company_repository.CompanyRepository,
    ):
        """Creates the resolver.

        Args:
            maintainer (instrument_index_maintainer.InstrumentIndexMaintainer): Holds the instrument index.
            client (rest_client.UnifiedBrokerInterfaceClient): Reads broker attributes such as the ISIN from UBI.
            companies (company_repository.CompanyRepository): Holds the companies imported from NSE's equity list.
        """
        self._maintainer = maintainer
        self._client = client
        self._companies = companies

    async def resolve(
        self, instrument_id: str
    ) -> company_identity.CompanyIdentity:
        """Finds the company an instrument belongs to.

        The NSE equity list is tried first, by symbol, because it has the full name and ISIN. Otherwise the ISIN and name come from the brokers' attributes in UBI, and a company without an ISIN is keyed as "exchange:symbol".

        Args:
            instrument_id (str): UBI's instrument id.

        Returns:
            company_identity.CompanyIdentity: The company.

        Raises:
            LookupError: The instrument index is not ready, or does not know the instrument.
            NotACompanyError: The instrument is an index, commodity, currency or bond.
        """
        index = self._maintainer.current_index
        if index is None:
            raise LookupError('The instrument index is not ready yet.')
        record = await asyncio.to_thread(index.instrument, instrument_id)
        if record is None:
            raise LookupError(f'No instrument {instrument_id} is in the index.')
        if (
            record['is_index']
            or record['bare_segment'] not in _COMPANY_SEGMENTS
        ):
            raise NotACompanyError(
                f'{record["display_name"]} is not a company, so there is no company knowledge to fetch.'
            )
        symbol = record['symbol'] or record['underlying_symbol']
        listed = await self._companies.find_by_symbol(symbol)
        if listed is not None:
            return company_identity.CompanyIdentity(
                listed['company_key'],
                listed['name'],
                listed.get('isin'),
                'nse',
                symbol,
            )
        isin = None
        name = symbol
        security = record
        if record['shape'] != 'security':
            security = await asyncio.to_thread(
                index.underlying_security,
                record['exchange'],
                symbol,
            )
        if security is not None:
            try:
                attributes = await self._client.additional_details(
                    security['instrument_id']
                )
            except exceptions.UnifiedBrokerInterfaceError:
                attributes = {}
            for entry in attributes.get('carried_by') or []:
                isin = isin or entry.get('isin')
                if name == symbol and entry.get('display_name'):
                    name = entry['display_name']
        company_key = isin or f'{record["exchange"]}:{symbol}'
        return company_identity.CompanyIdentity(
            company_key,
            name,
            isin,
            record['exchange'],
            symbol,
        )
