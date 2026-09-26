"""The routes that fetch, store and search company knowledge.

Typical usage example:

  web_application.include_router(KnowledgeRoutes(parts, guard).router)
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import anthropic
import fastapi
import httpx
import pydantic

from instruments_explorer.knowledge import company_resolver
from instruments_explorer.knowledge import fetch_job_runner
from instruments_explorer.knowledge import headquarters_sweep
from instruments_explorer.knowledge import key_people_book
from instruments_explorer.knowledge import key_people_extractor
from instruments_explorer.knowledge import knowledge_service
from instruments_explorer.knowledge import listing_importer
from instruments_explorer.knowledge import polite_client
from instruments_explorer.knowledge import postcode_geocoder
from instruments_explorer.knowledge import text_extractor
from instruments_explorer.knowledge import vector_store
from instruments_explorer.security import session_guard
from instruments_explorer.storage import company_repository
from instruments_explorer.storage import document_repository
from instruments_explorer.storage import fetch_job_repository

MAXIMUM_SEARCH_RESULTS = 50
COMPANY_DOCUMENTS = 60


class FetchRequest(pydantic.BaseModel):
    """The body of a request to fetch a company's knowledge.

    Attributes:
        sources: The fetcher keys to run, or None for every available fetcher.
    """

    sources: list[str] | None = None


class ExtractRequest(pydantic.BaseModel):
    """The body of a request to read key people from an uploaded document.

    Attributes:
        document_id: The uploaded document's id.
    """

    document_id: str = pydantic.Field(min_length=1, max_length=200)


class KnowledgeParts:
    """The components the knowledge routes use, gathered so the route class takes one argument.

    Attributes:
        resolver: Finds an instrument's company.
        service: Stores and searches knowledge.
        runner: Queues and runs fetch jobs.
        importer: Imports NSE's equity list.
        companies: Reads company documents.
        documents: Reads stored documents.
        jobs: Reads fetch jobs.
        after_listing_import: Called after an import so the instrument index picks up the new names.
    """

    def __init__(
        self,
        resolver: company_resolver.CompanyResolver,
        service: knowledge_service.KnowledgeService,
        runner: fetch_job_runner.FetchJobRunner,
        importer: listing_importer.ListingImporter,
        companies: company_repository.CompanyRepository,
        documents: document_repository.DocumentRepository,
        jobs: fetch_job_repository.FetchJobRepository,
        after_listing_import: Callable[[], Awaitable[None]],
        geocoder: postcode_geocoder.PostcodeGeocoder | None = None,
        people_extractor: key_people_extractor.KeyPeopleExtractor | None = None,
        sweep: headquarters_sweep.HeadquartersSweep | None = None,
    ):
        """Gathers the components.

        Args:
            resolver (company_resolver.CompanyResolver): Finds an instrument's company.
            service (knowledge_service.KnowledgeService): Stores and searches knowledge.
            runner (fetch_job_runner.FetchJobRunner): Queues and runs fetch jobs.
            importer (listing_importer.ListingImporter): Imports NSE's equity list.
            companies (company_repository.CompanyRepository): Reads company documents.
            documents (document_repository.DocumentRepository): Reads stored documents.
            jobs (fetch_job_repository.FetchJobRepository): Reads fetch jobs.
            after_listing_import (Callable[[], Awaitable[None]]): Called after an import.
            geocoder (postcode_geocoder.PostcodeGeocoder | None): Places headquarters on the map, or None.
            people_extractor (key_people_extractor.KeyPeopleExtractor | None): Reads key people from uploads with Claude, or None when no API key is set.
            sweep (headquarters_sweep.HeadquartersSweep | None): Locates every index company, or None.
        """
        self.resolver = resolver
        self.service = service
        self.runner = runner
        self.importer = importer
        self.companies = companies
        self.documents = documents
        self.jobs = jobs
        self.after_listing_import = after_listing_import
        self.geocoder = geocoder
        self.people_extractor = people_extractor
        self.sweep = sweep


class KnowledgeRoutes:
    """The /api/knowledge routes.

    Attributes:
        parts: The components the routes use.
        router: The FastAPI router holding the routes.
    """

    def __init__(
        self,
        parts: KnowledgeParts,
        guard: session_guard.SessionGuard,
    ):
        """Creates the routes.

        Args:
            parts (KnowledgeParts): The components the routes use.
            guard (session_guard.SessionGuard): Requires a logged-in session, and the application header on POST routes.
        """
        self.parts = parts
        self._background_tasks = set()
        self._book = key_people_book.KeyPeopleBook()
        session = fastapi.Depends(guard.require_session)
        header = fastapi.Depends(guard.require_app_header)
        self.router = fastapi.APIRouter(
            dependencies=[
                session,
            ],
        )
        for path, handler in [
            (
                '/api/knowledge/overview',
                self.overview,
            ),
            (
                '/api/knowledge/companies',
                self.companies,
            ),
            (
                '/api/knowledge/instruments/{instrument_id}',
                self.instrument_company,
            ),
            (
                '/api/knowledge/jobs',
                self.jobs,
            ),
            (
                '/api/knowledge/search',
                self.search,
            ),
            (
                '/api/knowledge/documents/{document_id}',
                self.document,
            ),
        ]:
            self.router.add_api_route(
                path,
                handler,
                methods=[
                    'GET',
                ],
            )
        for path, handler in [
            (
                '/api/knowledge/listing/refresh',
                self.refresh_listing,
            ),
            (
                '/api/knowledge/instruments/{instrument_id}/fetch',
                self.fetch,
            ),
            (
                '/api/knowledge/instruments/{instrument_id}/documents',
                self.upload,
            ),
            (
                '/api/knowledge/instruments/{instrument_id}/key-people/extract',
                self.extract_people,
            ),
        ]:
            self.router.add_api_route(
                path,
                handler,
                methods=[
                    'POST',
                ],
                dependencies=[
                    header,
                ],
            )

    async def overview(self) -> dict[str, Any]:
        """Describes what is stored, the sources and the latest jobs.

        Returns:
            dict[str, Any]: "counts", "sources" and "jobs".
        """
        return {
            'counts': await self.parts.service.counts(),
            'sources': self.parts.runner.describe_fetchers(),
            'jobs': await self.parts.jobs.recent(20),
        }

    async def refresh_listing(self) -> dict[str, Any]:
        """Imports NSE's equity list and the Nifty Total Market industries again, then rebuilds the instrument index in the background with the names and sectors.

        Returns:
            dict[str, Any]: "companies", the number imported, and "classified", the number given an industry.

        Raises:
            fastapi.HTTPException: 502 when NSE could not be read.
        """
        try:
            count = await self.parts.importer.import_nse()
            classified = await self.parts.importer.import_sectors()
        except (
            httpx.HTTPError,
            polite_client.RobotsDisallowedError,
            ValueError,
        ) as error:
            raise fastapi.HTTPException(
                status_code=502,
                detail=f'NSE’s equity list could not be imported: {error}',
            ) from error
        task = asyncio.create_task(self.parts.after_listing_import())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return {
            'companies': count,
            'classified': classified,
        }

    async def companies(
        self, q: str = '', limit: int = 30
    ) -> list[dict[str, Any]]:
        """Finds companies by name or symbol, or lists the latest fetched.

        Args:
            q (str): Typed text.
            limit (int): The largest number of companies, from 1 to 100.

        Returns:
            list[dict[str, Any]]: Company documents.

        Raises:
            fastapi.HTTPException: 400 for an invalid limit.
        """
        if limit < 1 or limit > 100:
            raise fastapi.HTTPException(
                status_code=400,
                detail=f'The limit must be between 1 and 100: {limit=}',
            )
        return await self.parts.companies.search(q, limit)

    async def instrument_company(self, instrument_id: str) -> dict[str, Any]:
        """Describes the company an instrument belongs to, with what is stored about it.

        Args:
            instrument_id (str): UBI's instrument id.

        Returns:
            dict[str, Any]: "company" (the identity, or None when the instrument is not a company), "reason" (why not), "profile" (the stored company document, or None), "key_people" (executives and board merged across sources), "headquarters" (the address with "location" when it can be placed on the map), "can_read_people" (whether uploads can be read with Claude) and "documents".

        Raises:
            fastapi.HTTPException: 404 for an unknown instrument, 503 while the index is not ready.
        """
        try:
            company = await self.parts.resolver.resolve(instrument_id)
        except company_resolver.NotACompanyError as error:
            return {
                'company': None,
                'reason': str(error),
                'profile': None,
                'key_people': None,
                'headquarters': None,
                'can_read_people': False,
                'documents': [],
            }
        except LookupError as error:
            status = 503 if 'not ready' in str(error) else 404
            raise fastapi.HTTPException(
                status_code=status,
                detail=str(error),
            ) from error
        profile = await self.parts.companies.find(company.company_key)
        return {
            'company': company.describe(),
            'reason': None,
            'profile': profile,
            'key_people': self._book.arrange(
                (profile or {}).get('key_people') or {}
            ),
            'headquarters': self.locate((profile or {}).get('headquarters')),
            'can_read_people': self.parts.people_extractor is not None,
            'documents': await self.parts.documents.for_company(
                company.company_key,
                COMPANY_DOCUMENTS,
            ),
        }

    async def fetch(
        self,
        instrument_id: str,
        body: FetchRequest,
    ) -> dict[str, Any]:
        """Queues a fetch job for the company an instrument belongs to.

        Args:
            instrument_id (str): UBI's instrument id.
            body (FetchRequest): Which sources to run.

        Returns:
            dict[str, Any]: The job.

        Raises:
            fastapi.HTTPException: 400 for an unknown source or an instrument that is not a company, 404 for an unknown instrument.
        """
        company = await self._company(instrument_id)
        try:
            return await self.parts.runner.submit(
                company, body.sources, 'requested'
            )
        except ValueError as error:
            raise fastapi.HTTPException(
                status_code=400,
                detail=str(error),
            ) from error

    async def upload(
        self,
        instrument_id: str,
        file: fastapi.UploadFile,
    ) -> dict[str, Any]:
        """Stores an uploaded file's text as a document of the instrument's company.

        Args:
            instrument_id (str): UBI's instrument id.
            file (fastapi.UploadFile): The uploaded file.

        Returns:
            dict[str, Any]: The stored document's id, title, length and chunk count.

        Raises:
            fastapi.HTTPException: 400 for an unreadable file or an instrument that is not a company, 404 for an unknown instrument, 503 when ChromaDB cannot be reached.
        """
        company = await self._company(instrument_id)
        data = await file.read(knowledge_service.MAXIMUM_UPLOAD_BYTES + 1)
        try:
            return await self.parts.service.import_upload(
                company,
                file.filename or 'upload.txt',
                data,
            )
        except text_extractor.UnsupportedFileError as error:
            raise fastapi.HTTPException(
                status_code=400,
                detail=str(error),
            ) from error
        except vector_store.VECTOR_STORE_ERRORS as error:
            raise fastapi.HTTPException(
                status_code=503,
                detail=f'The document could not be embedded: {error}',
            ) from error

    async def jobs(self, limit: int = 30) -> list[dict[str, Any]]:
        """Lists the latest fetch jobs.

        Args:
            limit (int): The largest number of jobs, from 1 to 100.

        Returns:
            list[dict[str, Any]]: The jobs, newest first.

        Raises:
            fastapi.HTTPException: 400 for an invalid limit.
        """
        if limit < 1 or limit > 100:
            raise fastapi.HTTPException(
                status_code=400,
                detail=f'The limit must be between 1 and 100: {limit=}',
            )
        return await self.parts.jobs.recent(limit)

    async def search(
        self,
        q: str,
        company_key: str | None = None,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        """Finds the stored passages closest in meaning to a question.

        Args:
            q (str): The question or phrase.
            company_key (str | None): Search only this company, or every company when absent.
            limit (int): The largest number of passages, from 1 to MAXIMUM_SEARCH_RESULTS.

        Returns:
            list[dict[str, Any]]: The passages, best first.

        Raises:
            fastapi.HTTPException: 400 for an empty question or invalid limit, 503 when ChromaDB cannot be reached.
        """
        if not q.strip():
            raise fastapi.HTTPException(
                status_code=400,
                detail='Type a question or phrase to search for.',
            )
        if limit < 1 or limit > MAXIMUM_SEARCH_RESULTS:
            raise fastapi.HTTPException(
                status_code=400,
                detail=f'The limit must be between 1 and {MAXIMUM_SEARCH_RESULTS}: {limit=}',
            )
        try:
            return await self.parts.service.search(q, company_key, limit)
        except vector_store.VECTOR_STORE_ERRORS as error:
            raise fastapi.HTTPException(
                status_code=503,
                detail=f'ChromaDB could not be searched: {error}',
            ) from error

    async def document(self, document_id: str) -> dict[str, Any]:
        """Reads one stored document with its full text.

        Args:
            document_id (str): The document's id.

        Returns:
            dict[str, Any]: The document.

        Raises:
            fastapi.HTTPException: 404 for an unknown document.
        """
        document = await self.parts.documents.find(document_id)
        if document is None:
            raise fastapi.HTTPException(
                status_code=404,
                detail=f'No document {document_id} is stored.',
            )
        return document

    def locate(
        self, headquarters: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """Adds map coordinates to a stored headquarters address.

        Args:
            headquarters (dict[str, Any] | None): The stored address, or None.

        Returns:
            dict[str, Any] | None: A copy with "location" (latitude, longitude, precision and place, or None when it cannot be placed) and "geocoder_ready", or None when there is no address.
        """
        if not headquarters:
            return None
        located = dict(headquarters)
        geocoder = self.parts.geocoder
        located['geocoder_ready'] = (
            geocoder is not None and geocoder.available()
        )
        located['location'] = None
        if located['geocoder_ready']:
            located['location'] = geocoder.locate(
                headquarters.get('postcode'),
                headquarters.get('city'),
                headquarters.get('country'),
            )
        return located

    async def extract_people(
        self,
        instrument_id: str,
        body: ExtractRequest,
    ) -> dict[str, Any]:
        """Reads the key people named in one of the company's uploaded documents with Claude, and stores them.

        Args:
            instrument_id (str): UBI's instrument id.
            body (ExtractRequest): The document to read.

        Returns:
            dict[str, Any]: "found", the number of people read, and "key_people", the merged executives and board.

        Raises:
            fastapi.HTTPException: 503 without an API key, 404 for an unknown document, 400 for a document of another company or one that names nobody, 429 when today's token limit is used up, 502 when Claude fails.
        """
        extractor = self.parts.people_extractor
        if extractor is None:
            raise fastapi.HTTPException(
                status_code=503,
                detail='Reading key people from documents needs the Claude API key in INSTRUMENTS_EXPLORER_ANTHROPIC_API_KEY.',
            )
        company = await self._company(instrument_id)
        document = await self.parts.documents.find(body.document_id)
        if document is None:
            raise fastapi.HTTPException(
                status_code=404,
                detail=f'No such document: {body.document_id!r}',
            )
        if document.get('company_key') != company.company_key:
            raise fastapi.HTTPException(
                status_code=400,
                detail='That document belongs to another company.',
            )
        try:
            people = await extractor.extract(
                company.name, document.get('text') or ''
            )
        except key_people_extractor.ExtractionError as error:
            status = 429 if 'limit' in str(error) else 400
            raise fastapi.HTTPException(
                status_code=status, detail=str(error)
            ) from error
        except anthropic.APIError as error:
            raise fastapi.HTTPException(
                status_code=502,
                detail=f'The Claude API failed: {error}',
            ) from error
        await self.parts.service.store_extracted_people(
            company,
            people,
            document.get('title') or 'an uploaded document',
        )
        profile = await self.parts.companies.find(company.company_key) or {}
        return {
            'found': len(people),
            'key_people': self._book.arrange(profile.get('key_people') or {}),
        }

    async def _company(self, instrument_id: str) -> Any:
        """Resolves an instrument's company for a POST route.

        Args:
            instrument_id (str): UBI's instrument id.

        Returns:
            Any: The CompanyIdentity.

        Raises:
            fastapi.HTTPException: 400 when the instrument is not a company, 404 for an unknown instrument, 503 while the index is not ready.
        """
        try:
            return await self.parts.resolver.resolve(instrument_id)
        except company_resolver.NotACompanyError as error:
            raise fastapi.HTTPException(
                status_code=400,
                detail=str(error),
            ) from error
        except LookupError as error:
            status = 503 if 'not ready' in str(error) else 404
            raise fastapi.HTTPException(
                status_code=status,
                detail=str(error),
            ) from error
