"""Stores what the fetchers find, and searches it.

A fetcher's profile fields are merged into the company document, its documents are stored in MongoDB, and each new or changed document is split into chunks and embedded in ChromaDB.

Typical usage example:

  service = KnowledgeService(companies, documents, vector_store, clock)
  summary = await service.store(company, 'screener', result)
  hits = await service.search('who makes refinery products', None, 10)
"""

import asyncio
from typing import Any

from instruments_explorer.knowledge import chunker
from instruments_explorer.knowledge import company_identity
from instruments_explorer.knowledge import fetched_document
from instruments_explorer.knowledge import key_people_book
from instruments_explorer.knowledge import text_extractor
from instruments_explorer.knowledge import vector_store
from instruments_explorer.storage import company_repository
from instruments_explorer.storage import document_repository
from instruments_explorer.utilities import clock

UPLOAD_SOURCE = 'upload'
PEOPLE_SOURCE = 'key_people'
PEOPLE_UPLOAD_SOURCE = 'people_upload'
MAXIMUM_UPLOAD_BYTES = 30 * 1024 * 1024


class KnowledgeService:
    """Connects the fetchers' results to MongoDB and ChromaDB."""

    def __init__(
        self,
        companies: company_repository.CompanyRepository,
        documents: document_repository.DocumentRepository,
        store: vector_store.VectorStore,
        time_source: clock.SystemClock,
    ):
        """Creates the service.

        Args:
            companies (company_repository.CompanyRepository): Stores company documents.
            documents (document_repository.DocumentRepository): Stores fetched and uploaded documents.
            store (vector_store.VectorStore): Embeds and searches document chunks.
            time_source (clock.SystemClock): The source of the current time.
        """
        self._companies = companies
        self._documents = documents
        self._store = store
        self._time_source = time_source
        self._chunker = chunker.Chunker()
        self._extractor = text_extractor.TextExtractor()
        self._book = key_people_book.KeyPeopleBook()

    async def store(
        self,
        company: company_identity.CompanyIdentity,
        source: str,
        result: fetched_document.FetchResult,
    ) -> dict[str, int]:
        """Stores one fetcher's result for a company.

        Args:
            company (company_identity.CompanyIdentity): The company.
            source (str): The fetcher's key.
            result (fetched_document.FetchResult): What the fetcher found.

        Returns:
            dict[str, int]: "documents" (stored), "new" (not stored before) and "chunks" (embedded).
        """
        fetched_at = self._time_source.now()
        profile = dict(result.profile)
        profile['name'] = company.name
        profile['symbol'] = company.symbol
        profile['exchange'] = company.exchange
        if company.isin:
            profile['isin'] = company.isin
        await self._companies.merge(
            company.company_key,
            profile,
            source,
            fetched_at,
            result.message,
        )
        new = 0
        chunks = 0
        if self._touches_people(result.profile):
            passage = await self._people_passage(company)
            if passage is not None:
                result = fetched_document.FetchResult(
                    result.profile,
                    [
                        *result.documents,
                        passage,
                    ],
                    result.message,
                )
        for document in result.documents:
            record = document.to_record(company.company_key, fetched_at)
            if await self._documents.upsert(record):
                new += 1
            chunks += await self._embed(company, document)
        return {
            'documents': len(result.documents),
            'new': new,
            'chunks': chunks,
        }

    async def store_extracted_people(
        self,
        company: company_identity.CompanyIdentity,
        people: list[dict[str, Any]],
        document_title: str,
    ) -> None:
        """Stores the key people Claude read from an uploaded document, replacing those read from an earlier upload.

        Args:
            company (company_identity.CompanyIdentity): The company.
            people (list[dict[str, Any]]): One {"name", "role"} per person.
            document_title (str): The document they were read from.
        """
        await self.store(
            company,
            PEOPLE_UPLOAD_SOURCE,
            fetched_document.FetchResult(
                {
                    'key_people.upload': people,
                    'key_people_upload_document': document_title,
                },
                [],
                f'{len(people)} people read from {document_title}',
            ),
        )

    def _touches_people(self, profile: dict[str, Any]) -> bool:
        """Says whether a fetch changed the key people or the headquarters.

        Args:
            profile (dict[str, Any]): The fetched profile fields.

        Returns:
            bool: True when the searchable key people passage needs rewriting.
        """
        for field in profile:
            if field == 'headquarters' or field.startswith('key_people.'):
                return True
        return False

    async def _people_passage(
        self,
        company: company_identity.CompanyIdentity,
    ) -> fetched_document.FetchedDocument | None:
        """Writes the company's key people and headquarters as one searchable document, which replaces the previous version.

        Args:
            company (company_identity.CompanyIdentity): The company.

        Returns:
            fetched_document.FetchedDocument | None: The passage, or None when nothing is known yet.
        """
        stored = await self._companies.find(company.company_key) or {}
        arranged = self._book.arrange(stored.get('key_people') or {})
        headquarters = stored.get('headquarters')
        if (
            not arranged['executives']
            and not arranged['board']
            and not headquarters
        ):
            return None
        return fetched_document.FetchedDocument(
            PEOPLE_SOURCE,
            f'{company.name}: key people and headquarters',
            '',
            self._time_source.now(),
            self._book.describe(company.name, arranged, headquarters),
            identity=f'key_people:{company.company_key}',
        )

    async def import_upload(
        self,
        company: company_identity.CompanyIdentity,
        filename: str,
        data: bytes,
    ) -> dict[str, Any]:
        """Reads an uploaded file's text and stores it as a company document.

        Args:
            company (company_identity.CompanyIdentity): The company.
            filename (str): The file's name.
            data (bytes): The file's content.

        Returns:
            dict[str, Any]: "document_id", "title", "characters" and "chunks".

        Raises:
            text_extractor.UnsupportedFileError: The file type cannot be read, or the file is empty or too large.
        """
        if not data:
            raise text_extractor.UnsupportedFileError('The file is empty.')
        if len(data) > MAXIMUM_UPLOAD_BYTES:
            raise text_extractor.UnsupportedFileError(
                f'Files larger than {MAXIMUM_UPLOAD_BYTES // (1024 * 1024)} MB are not accepted.'
            )
        text = await asyncio.to_thread(self._extractor.extract, filename, data)
        if not text.strip():
            raise text_extractor.UnsupportedFileError(
                f'No text could be read from {filename!r}; a scanned PDF has pictures of text rather than text.'
            )
        document = fetched_document.FetchedDocument(
            UPLOAD_SOURCE,
            filename,
            '',
            self._time_source.now(),
            text,
        )
        summary = await self.store(
            company,
            UPLOAD_SOURCE,
            fetched_document.FetchResult(
                {}, [document], f'Uploaded {filename}'
            ),
        )
        return {
            'document_id': document.document_id,
            'title': filename,
            'characters': len(text),
            'chunks': summary['chunks'],
        }

    async def search(
        self,
        text: str,
        company_key: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Finds the passages closest in meaning to a question.

        Args:
            text (str): The question or phrase.
            company_key (str | None): Search only this company, or None for every company.
            limit (int): The largest number of passages.

        Returns:
            list[dict[str, Any]]: One passage per hit with "text", "score" (1 for identical meaning, lower for further), "document_id", "company_key", "symbol", "source", "title", "url" and "published_at", best first.
        """
        hits = await asyncio.to_thread(
            self._store.query, text, company_key, limit
        )
        results = []
        for hit in hits:
            metadata = hit['metadata'] or {}
            results.append(
                {
                    'text': hit['text'],
                    'score': round(1.0 - float(hit['distance']), 4),
                    'document_id': metadata.get('document_id'),
                    'company_key': metadata.get('company_key'),
                    'symbol': metadata.get('symbol'),
                    'source': metadata.get('source'),
                    'title': metadata.get('title'),
                    'url': metadata.get('url'),
                    'published_at': metadata.get('published_at'),
                }
            )
        return results

    async def counts(self) -> dict[str, Any]:
        """Counts what is stored.

        Returns:
            dict[str, Any]: "listed", "classified" and "fetched" companies, "documents", and "chunks" (None when ChromaDB cannot be reached).
        """
        companies = await self._companies.counts()
        try:
            chunks = await asyncio.to_thread(self._store.count)
        except vector_store.VECTOR_STORE_ERRORS:
            chunks = None
        return {
            'listed': companies['listed'],
            'classified': companies['classified'],
            'fetched': companies['fetched'],
            'documents': await self._documents.count(),
            'chunks': chunks,
        }

    async def _embed(
        self,
        company: company_identity.CompanyIdentity,
        document: fetched_document.FetchedDocument,
    ) -> int:
        """Splits a document into chunks and embeds them, replacing any earlier chunks of the same document.

        Args:
            company (company_identity.CompanyIdentity): The company.
            document (fetched_document.FetchedDocument): The document.

        Returns:
            int: The number of chunks embedded.
        """
        chunks = self._chunker.split(document.text)
        metadata = {
            'company_key': company.company_key,
            'symbol': company.symbol,
            'source': document.source,
            'title': document.title[:300],
            'url': document.url,
            'published_at': document.published_at,
        }
        return await asyncio.to_thread(
            self._store.add,
            document.document_id,
            chunks,
            metadata,
        )
