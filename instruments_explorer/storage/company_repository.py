"""The companies collection: one document per company, keyed by ISIN where known.

A company document grows as sources report on it: the NSE listing gives its name and ISIN, yfinance its sector and fundamentals, Screener.in its ratios and industry classification, and so on. Each source's part is merged in with `$set`, so sources never overwrite each other's fields.

Typical usage example:

  companies = CompanyRepository(connection.database())
  await companies.merge('INE002A01018', {'sector': 'Energy'}, 'yahoo', now)
"""

import re
from collections.abc import Iterable, Mapping
from typing import Any

_COLLECTION = 'companies'


class CompanyRepository:
    """Reads and writes company documents in the project's own MongoDB."""

    def __init__(self, database: Any):
        """Wraps the project's database.

        Args:
            database (Any): A pymongo AsyncDatabase, or a stand-in with the same collection methods.
        """
        self._collection = database[_COLLECTION]

    async def ensure_indexes(self) -> None:
        """Creates the indexes the lookups use."""
        await self._collection.create_index('symbol')
        await self._collection.create_index('name_key')

    async def upsert_listings(
        self,
        listings: Iterable[Mapping[str, Any]],
        imported_at: float,
    ) -> int:
        """Stores or refreshes companies from an exchange's list of listed equities.

        Args:
            listings (Iterable[Mapping[str, Any]]): One mapping per company with "company_key", "name", "isin", "exchange", "symbol" and optionally "listed_on" and "face_value".
            imported_at (float): When the list was read, in epoch seconds.

        Returns:
            int: The number of companies stored.
        """
        count = 0
        for listing in listings:
            fields = dict(listing)
            fields['name_key'] = self.name_key(str(listing.get('name') or ''))
            fields['listing_imported_at'] = imported_at
            await self._collection.update_one(
                {
                    '_id': listing['company_key'],
                },
                {
                    '$set': fields,
                },
                upsert=True,
            )
            count += 1
        return count

    async def set_index_industries(
        self,
        constituents: Iterable[Mapping[str, Any]],
        imported_at: float,
    ) -> int:
        """Marks the Nifty Total Market constituents and stores the industry NSE gives each.

        Companies no longer in the list lose their mark, so the screener's default universe follows the index. The index's own short name is kept as "index_name", apart from the registered name the equity list gives.

        Args:
            constituents (Iterable[Mapping[str, Any]]): One mapping per company with "company_key", "name", "industry", "symbol" and "isin".
            imported_at (float): When the list was read, in epoch seconds.

        Returns:
            int: The number of companies marked.
        """
        keys = set()
        for constituent in constituents:
            keys.add(constituent['company_key'])
            await self._collection.update_one(
                {
                    '_id': constituent['company_key'],
                },
                {
                    '$set': {
                        'company_key': constituent['company_key'],
                        'symbol': constituent['symbol'],
                        'isin': constituent['isin'],
                        'nse_industry': constituent['industry'],
                        'index_name': constituent['name'],
                        'total_market': True,
                        'industries_imported_at': imported_at,
                    },
                },
                upsert=True,
            )
        cursor = self._collection.find(
            {
                'total_market': True,
            }
        )
        async for document in cursor:
            if document['_id'] not in keys:
                await self._collection.update_one(
                    {
                        '_id': document['_id'],
                    },
                    {
                        '$set': {
                            'total_market': False,
                        },
                    },
                )
        return len(keys)

    async def merge(
        self,
        company_key: str,
        fields: Mapping[str, Any],
        source: str,
        fetched_at: float,
        message: str = '',
    ) -> None:
        """Merges one source's findings into a company, recording when and how the source ran.

        Args:
            company_key (str): The company's key.
            fields (Mapping[str, Any]): The fields the source found, which replace those same fields only.
            source (str): The source's key, such as "yahoo".
            fetched_at (float): When the source ran, in epoch seconds.
            message (str): What the source reported, such as how many articles it found.
        """
        update = dict(fields)
        update['company_key'] = company_key
        update[f'sources.{source}'] = {
            'fetched_at': fetched_at,
            'message': message,
        }
        update['updated_at'] = fetched_at
        await self._collection.update_one(
            {
                '_id': company_key,
            },
            {
                '$set': update,
            },
            upsert=True,
        )

    async def find(self, company_key: str) -> dict[str, Any] | None:
        """Reads one company.

        Args:
            company_key (str): The company's key.

        Returns:
            dict[str, Any] | None: The company document without its _id, or None.
        """
        document = await self._collection.find_one(
            {
                '_id': company_key,
            }
        )
        return self._clean(document)

    async def find_by_symbol(self, symbol: str) -> dict[str, Any] | None:
        """Reads the company listed under a trading symbol.

        Args:
            symbol (str): The NSE symbol, such as "RELIANCE".

        Returns:
            dict[str, Any] | None: The company document without its _id, or None.
        """
        document = await self._collection.find_one(
            {
                'symbol': symbol,
            }
        )
        return self._clean(document)

    async def details_by_symbol(self) -> dict[str, dict[str, str | None]]:
        """Reads every known company's name and sector by symbol, for the instrument search index and the screener.

        Returns:
            dict[str, dict[str, str | None]]: {"name", "sector"} by NSE symbol.
        """
        details = {}
        cursor = self._collection.find(
            {
                'symbol': {
                    '$exists': True,
                },
            }
        )
        async for document in cursor:
            symbol = document.get('symbol')
            if not symbol:
                continue
            details[symbol] = {
                'name': document.get('name') or document.get('index_name'),
                'sector': self.sector(document),
            }
        return details

    async def screener_members(
        self, only_total_market: bool
    ) -> list[dict[str, Any]]:
        """Lists the companies a screener universe covers.

        Args:
            only_total_market (bool): True for Nifty Total Market constituents only, False for every company in NSE's equity list.

        Returns:
            list[dict[str, Any]]: Company documents without their _id.
        """
        if only_total_market:
            query = {
                'total_market': True,
            }
        else:
            query = {
                'listing_imported_at': {
                    '$exists': True,
                },
            }
        members = []
        async for document in self._collection.find(query):
            if document.get('symbol'):
                members.append(self._clean(document))
        return members

    def sector(self, document: Mapping[str, Any]) -> str | None:
        """Chooses a company's sector from what its sources report.

        NSE's index industry comes first because it covers the most companies with one consistent vocabulary; Screener.in's top-level classification and Yahoo's sector follow for companies outside the index.

        Args:
            document (Mapping[str, Any]): The company document.

        Returns:
            str | None: The sector, or None when no source reports one.
        """
        if document.get('nse_industry'):
            return document['nse_industry']
        classification = document.get('classification') or []
        if classification:
            return classification[0]
        return document.get('sector')

    async def search(self, text: str, limit: int) -> list[dict[str, Any]]:
        """Finds companies whose name or symbol starts with typed text, or the most recently fetched ones when nothing is typed.

        Args:
            text (str): The typed text.
            limit (int): The largest number of companies.

        Returns:
            list[dict[str, Any]]: Company documents without their _id.
        """
        key = self.name_key(text)
        if key:
            query = {
                '$or': [
                    {
                        'name_key': {
                            '$regex': f'^{re.escape(key)}',
                        },
                    },
                    {
                        'symbol': {
                            '$regex': f'^{re.escape(text.strip().upper())}',
                        },
                    },
                ],
            }
            cursor = (
                self._collection.find(query).sort('name_key', 1).limit(limit)
            )
        else:
            query = {
                'updated_at': {
                    '$exists': True,
                },
            }
            cursor = (
                self._collection.find(query).sort('updated_at', -1).limit(limit)
            )
        companies = []
        async for document in cursor:
            companies.append(self._clean(document))
        return companies

    async def fetched_keys(self) -> list[str]:
        """Lists the companies any source has reported on, for the periodic news refresh.

        Returns:
            list[str]: Company keys.
        """
        keys = []
        cursor = self._collection.find(
            {
                'updated_at': {
                    '$exists': True,
                },
            }
        )
        async for document in cursor:
            keys.append(document['_id'])
        return keys

    async def counts(self) -> dict[str, int]:
        """Counts listed companies and companies with fetched data.

        Returns:
            dict[str, int]: "listed", "classified" (given an NSE industry) and "fetched".
        """
        listed = await self._collection.count_documents(
            {
                'listing_imported_at': {
                    '$exists': True,
                },
            }
        )
        classified = await self._collection.count_documents(
            {
                'nse_industry': {
                    '$exists': True,
                },
            }
        )
        fetched = await self._collection.count_documents(
            {
                'updated_at': {
                    '$exists': True,
                },
            }
        )
        return {
            'listed': listed,
            'classified': classified,
            'fetched': fetched,
        }

    def name_key(self, name: str) -> str:
        """Normalises a name for prefix search.

        Args:
            name (str): A company name or typed text.

        Returns:
            str: The name in lower case with only letters, digits and single spaces.
        """
        words = re.findall(r'[0-9a-z]+', name.lower())
        return ' '.join(words)

    def _clean(
        self, document: Mapping[str, Any] | None
    ) -> dict[str, Any] | None:
        """Removes MongoDB's _id from a document.

        Args:
            document (Mapping[str, Any] | None): The stored document, or None.

        Returns:
            dict[str, Any] | None: A copy without _id, or None.
        """
        if document is None:
            return None
        cleaned = dict(document)
        cleaned.pop('_id', None)
        return cleaned
