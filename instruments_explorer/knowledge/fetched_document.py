"""What a fetcher hands back: profile fields for the company and documents to store and embed.

Typical usage example:

  result = FetchResult({'sector': 'Energy'}, [document], 'Found 12 articles.')
"""

import hashlib
from typing import Any


class FetchedDocument:
    """One piece of text about a company, such as an article, an announcement or a profile.

    Attributes:
        source: The fetcher's key, such as "rss_news".
        title: The title.
        url: Where it came from, or an empty string for text with no address.
        published_at: When it was published, in epoch seconds, or None.
        text: The text to store and embed.
        document_id: A stable id worked out from the source and the address or text, so fetching again replaces rather than duplicates.
    """

    def __init__(
        self,
        source: str,
        title: str,
        url: str,
        published_at: float | None,
        text: str,
    ):
        """Creates the document.

        Args:
            source (str): The fetcher's key.
            title (str): The title.
            url (str): Where it came from, or an empty string.
            published_at (float | None): When it was published, in epoch seconds, or None.
            text (str): The text.
        """
        self.source = source
        self.title = title
        self.url = url
        self.published_at = published_at
        self.text = text
        identity = url if url else f'{title}\n{text}'
        digest = hashlib.sha1(f'{source}\n{identity}'.encode()).hexdigest()
        self.document_id = digest

    def to_record(self, company_key: str, fetched_at: float) -> dict[str, Any]:
        """Writes the document as it is stored.

        Args:
            company_key (str): The company it belongs to.
            fetched_at (float): When it was fetched, in epoch seconds.

        Returns:
            dict[str, Any]: The stored fields.
        """
        return {
            'document_id': self.document_id,
            'company_key': company_key,
            'source': self.source,
            'title': self.title,
            'url': self.url,
            'published_at': self.published_at,
            'fetched_at': fetched_at,
            'text': self.text,
        }


class FetchResult:
    """Everything one fetcher found about one company.

    Attributes:
        profile: Fields to merge into the company document.
        documents: Documents to store and embed.
        message: A one-line summary of what happened, shown in the job list.
    """

    def __init__(
        self,
        profile: dict[str, Any],
        documents: list[FetchedDocument],
        message: str,
    ):
        """Creates the result.

        Args:
            profile (dict[str, Any]): Fields to merge into the company document.
            documents (list[FetchedDocument]): Documents to store and embed.
            message (str): A one-line summary of what happened.
        """
        self.profile = profile
        self.documents = documents
        self.message = message
