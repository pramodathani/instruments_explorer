"""The documents collection: every article, announcement, profile text and upload stored for a company.

Typical usage example:

  documents = DocumentRepository(connection.database())
  created = await documents.upsert(document)
"""

from collections.abc import Mapping
from typing import Any

_COLLECTION = 'documents'
_LIST_FIELDS = {
    'text': 0,
}


class DocumentRepository:
    """Reads and writes stored documents in the project's own MongoDB."""

    def __init__(self, database: Any):
        """Wraps the project's database.

        Args:
            database (Any): A pymongo AsyncDatabase, or a stand-in with the same collection methods.
        """
        self._collection = database[_COLLECTION]

    async def ensure_indexes(self) -> None:
        """Creates the indexes the lookups use."""
        await self._collection.create_index('company_key')
        await self._collection.create_index('source')

    async def upsert(self, document: Mapping[str, Any]) -> bool:
        """Stores a document, replacing an earlier copy with the same id.

        Args:
            document (Mapping[str, Any]): The document, with "document_id", "company_key", "source", "title", "url", "published_at", "fetched_at" and "text".

        Returns:
            bool: True when the document is new, False when it replaced an earlier copy.
        """
        existing = await self._collection.find_one(
            {
                '_id': document['document_id'],
            }
        )
        stored = dict(document)
        stored['_id'] = document['document_id']
        await self._collection.replace_one(
            {
                '_id': document['document_id'],
            },
            stored,
            upsert=True,
        )
        return existing is None

    async def find(self, document_id: str) -> dict[str, Any] | None:
        """Reads one document with its full text.

        Args:
            document_id (str): The document's id.

        Returns:
            dict[str, Any] | None: The document without its _id, or None.
        """
        document = await self._collection.find_one(
            {
                '_id': document_id,
            }
        )
        if document is None:
            return None
        cleaned = dict(document)
        cleaned.pop('_id', None)
        return cleaned

    async def for_company(
        self,
        company_key: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Lists a company's documents without their full text, newest first.

        Args:
            company_key (str): The company's key.
            limit (int): The largest number of documents.

        Returns:
            list[dict[str, Any]]: The documents, each without _id and text.
        """
        cursor = (
            self._collection.find(
                {
                    'company_key': company_key,
                },
                _LIST_FIELDS,
            )
            .sort('published_at', -1)
            .limit(limit)
        )
        documents = []
        async for document in cursor:
            cleaned = dict(document)
            cleaned.pop('_id', None)
            documents.append(cleaned)
        return documents

    async def count(self) -> int:
        """Counts every stored document.

        Returns:
            int: The number of documents.
        """
        return await self._collection.count_documents({})
