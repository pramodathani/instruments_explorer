"""Who a company is, as the knowledge fetchers need to know it.

Typical usage example:

  company = CompanyIdentity('INE002A01018', 'Reliance Industries Limited', 'INE002A01018', 'nse', 'RELIANCE')
"""

from typing import Any


class CompanyIdentity:
    """A company's key, name, ISIN and trading symbol.

    Attributes:
        company_key: The key its documents are stored under: the ISIN where known, otherwise "exchange:symbol".
        name: The company's name, or its symbol when no name is known.
        isin: The ISIN, or None.
        exchange: The exchange its shares are listed on, such as "nse".
        symbol: The trading symbol, such as "RELIANCE".
    """

    def __init__(
        self,
        company_key: str,
        name: str,
        isin: str | None,
        exchange: str,
        symbol: str,
    ):
        """Creates the identity.

        Args:
            company_key (str): The key its documents are stored under.
            name (str): The company's name.
            isin (str | None): The ISIN, or None.
            exchange (str): The exchange.
            symbol (str): The trading symbol.
        """
        self.company_key = company_key
        self.name = name
        self.isin = isin
        self.exchange = exchange
        self.symbol = symbol

    def short_name(self) -> str:
        """Gives the name without legal suffixes, for matching news headlines.

        Returns:
            str: The name without words such as "Limited", "Ltd" or "Private".
        """
        words = []
        for word in self.name.replace('.', ' ').split():
            if word.lower() not in (
                'limited',
                'ltd',
                'private',
                'pvt',
                'the',
                'co',
                'company',
                'corporation',
                'corp',
                'inc',
            ):
                words.append(word)
        if not words:
            return self.symbol
        return ' '.join(words)

    def describe(self) -> dict[str, Any]:
        """Describes the identity for the browser and for stored jobs.

        Returns:
            dict[str, Any]: "company_key", "name", "isin", "exchange" and "symbol".
        """
        return {
            'company_key': self.company_key,
            'name': self.name,
            'isin': self.isin,
            'exchange': self.exchange,
            'symbol': self.symbol,
        }
