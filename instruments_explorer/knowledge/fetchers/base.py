"""The shared shape of every knowledge fetcher.

Each source of company knowledge is its own fetcher class. This base holds only what they share: a key, a label, a description, and whether the fetcher can run with the current settings.

Typical usage example:

  fetcher = screener_in.ScreenerFetcher(polite_client)
  if fetcher.available()[0]:
      result = await fetcher.fetch(company)
"""

from typing import Any

from instruments_explorer.knowledge import company_identity
from instruments_explorer.knowledge import fetched_document


class BaseFetcher:
    """What every fetcher has; subclasses do the fetching.

    Attributes:
        key: The short name used in requests and stored with documents, such as "screener".
        label: The name shown to people, such as "Screener.in".
        description: One sentence on what the fetcher collects.
        news: Whether the fetcher collects news, which the periodic refresh repeats.
    """

    def __init__(self, key: str, label: str, description: str, news: bool):
        """Creates the fetcher's description.

        Args:
            key (str): The short name.
            label (str): The name shown to people.
            description (str): One sentence on what it collects.
            news (bool): Whether it collects news.
        """
        self.key = key
        self.label = label
        self.description = description
        self.news = news

    def available(self) -> tuple[bool, str]:
        """Says whether the fetcher can run with the current settings.

        Returns:
            tuple[bool, str]: A tuple (True and an empty string when it can run, or False and the reason it cannot).
        """
        return True, ''

    def describe(self) -> dict[str, Any]:
        """Describes the fetcher for the browser.

        Returns:
            dict[str, Any]: "key", "label", "description", "news", "available" and "reason".
        """
        available, reason = self.available()
        return {
            'key': self.key,
            'label': self.label,
            'description': self.description,
            'news': self.news,
            'available': available,
            'reason': reason,
        }

    async def fetch(
        self,
        company: company_identity.CompanyIdentity,
    ) -> fetched_document.FetchResult:
        """Collects what the source knows about a company.

        Args:
            company (company_identity.CompanyIdentity): The company.

        Returns:
            fetched_document.FetchResult: Profile fields, documents and a summary message.

        Raises:
            NotImplementedError: A subclass did not define the fetching.
        """
        raise NotImplementedError
