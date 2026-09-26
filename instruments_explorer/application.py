"""Builds every component of instruments_explorer and runs the web server.

Typical usage example:

  Application().run()
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Sequence

import anthropic
import fastapi
import httpx
import starlette.middleware.gzip
import starlette.middleware.sessions
import uvicorn

from instruments_explorer.assistant import assistant_services
from instruments_explorer.assistant import tool_box
from instruments_explorer.configuration import settings
from instruments_explorer.configuration import (
    unified_broker_interface_configuration,
)
from instruments_explorer.derivatives import option_chain_builder
from instruments_explorer.indicators import indicator_catalogue
from instruments_explorer.instruments import instrument_index_builder
from instruments_explorer.instruments import instrument_index_maintainer
from instruments_explorer.knowledge import company_resolver
from instruments_explorer.knowledge import fetch_job_runner
from instruments_explorer.knowledge import headquarters_sweep
from instruments_explorer.knowledge import key_people_extractor
from instruments_explorer.knowledge import knowledge_scheduler
from instruments_explorer.knowledge import knowledge_service
from instruments_explorer.knowledge import listing_importer
from instruments_explorer.knowledge import polite_client
from instruments_explorer.knowledge import postcode_geocoder
from instruments_explorer.knowledge import vector_store
from instruments_explorer.knowledge.fetchers import bing_news
from instruments_explorer.knowledge.fetchers import google_search
from instruments_explorer.knowledge.fetchers import nse_announcements
from instruments_explorer.knowledge.fetchers import rss_news
from instruments_explorer.knowledge.fetchers import screener_in
from instruments_explorer.knowledge.fetchers import wikipedia
from instruments_explorer.knowledge.fetchers import yahoo_fundamentals
from instruments_explorer.knowledge.fetchers import zaubacorp_directors
from instruments_explorer.market import live_quote_hub
from instruments_explorer.market import live_quote_reader
from instruments_explorer.market import quote_snapshot_reader
from instruments_explorer.routes import auth_routes
from instruments_explorer.routes import chart_routes
from instruments_explorer.routes import chat_routes
from instruments_explorer.routes import derivative_routes
from instruments_explorer.routes import earth_routes
from instruments_explorer.routes import frontend_routes
from instruments_explorer.routes import instrument_routes
from instruments_explorer.routes import knowledge_routes
from instruments_explorer.routes import live_routes
from instruments_explorer.routes import screener_routes
from instruments_explorer.routes import status_routes
from instruments_explorer.routes import universe_routes
from instruments_explorer.screener import screener_scheduler
from instruments_explorer.screener import screener_service
from instruments_explorer.screener import screener_universe
from instruments_explorer.screener import snapshot_job
from instruments_explorer.screener.conditions import condition_catalogue
from instruments_explorer.security import authenticator
from instruments_explorer.security import session_guard
from instruments_explorer.security import websocket_origin_checker
from instruments_explorer.storage import chat_usage_repository
from instruments_explorer.storage import chroma_connection
from instruments_explorer.storage import company_repository
from instruments_explorer.storage import conversation_repository
from instruments_explorer.storage import document_repository
from instruments_explorer.storage import fetch_job_repository
from instruments_explorer.storage import mongo_connection
from instruments_explorer.storage import screener_repository
from instruments_explorer.unified_broker_interface import catalogue_gateway
from instruments_explorer.unified_broker_interface import health_checker
from instruments_explorer.unified_broker_interface import live_quote_gateway
from instruments_explorer.unified_broker_interface import (
    tradingmachine_components,
)
from instruments_explorer.universe import universe_service
from instruments_explorer.utilities import clock

_SESSION_COOKIE = 'instruments_explorer_session'
_WEB_USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) instruments_explorer/0.1'
_ROBOTS_AGENT = 'instruments_explorer'
_LOGGER = logging.getLogger(__name__)


class Application:
    """The whole of instruments_explorer: its components and its web routes.

    Attributes:
        explorer_settings: The settings.
        time_source: The source of the current time.
    """

    def __init__(self, explorer_settings: settings.Settings | None = None):
        """Creates the application without connecting to anything.

        Args:
            explorer_settings (settings.Settings | None): The settings, or None to read them from the environment and .env.
        """
        if explorer_settings is None:
            explorer_settings = settings.Settings()
        self.explorer_settings = explorer_settings
        self.time_source = clock.SystemClock()
        self._mongo = None
        self._chroma = None
        self._tradingmachine = None
        self._maintainer = None
        self._quote_reader = None
        self._web_client = None
        self._knowledge_parts = None
        self._scheduler = None
        self._screener_scheduler = None

    def run(self) -> None:
        """Builds the application and serves it until stopped.

        Raises:
            ValueError: A setting or UBI's .env file is invalid.
            FileNotFoundError: UBI's .env file is missing.
        """
        logging.basicConfig(
            level=logging.INFO,
            format='%(levelname)-8s %(name)s %(message)s',
        )
        logging.getLogger('httpx').setLevel(logging.WARNING)
        web_application = self.build()
        uvicorn.run(
            web_application,
            host=self.explorer_settings.host,
            port=self.explorer_settings.port,
            workers=1,
            proxy_headers=False,
            log_config=None,
        )

    def build(self) -> fastapi.FastAPI:
        """Builds every real component and the FastAPI application.

        Returns:
            fastapi.FastAPI: The web application, whose lifespan runs the background work and closes every connection.

        Raises:
            ValueError: A setting or UBI's .env file is invalid.
            FileNotFoundError: UBI's .env file is missing.
        """
        explorer_settings = self.explorer_settings
        explorer_settings.require_security_values()
        self._mongo = mongo_connection.MongoConnection(explorer_settings)
        self._chroma = chroma_connection.ChromaConnection(explorer_settings)
        ubi_configuration = unified_broker_interface_configuration.UnifiedBrokerInterfaceConfiguration.load(
            explorer_settings.unified_broker_interface_directory
        )
        self._tradingmachine = (
            tradingmachine_components.TradingmachineComponents(
                ubi_configuration,
                explorer_settings.ubi_request_timeout_seconds,
                explorer_settings.ubi_may_connect,
                explorer_settings.ubi_connect_cooldown_seconds,
                self.time_source,
            )
        )
        client = catalogue_gateway.CatalogueGateway(
            self._tradingmachine.catalogue
        )
        quote_gateway = live_quote_gateway.LiveQuoteGateway(
            self._tradingmachine.live_quote_reader
        )
        database = self._mongo.database()
        companies = company_repository.CompanyRepository(database)
        builder = instrument_index_builder.InstrumentIndexBuilder(
            client,
            explorer_settings.data_directory / 'instruments',
            self.time_source,
        )
        self._maintainer = instrument_index_maintainer.InstrumentIndexMaintainer(
            client,
            builder,
            self.time_source,
            check_interval_seconds=explorer_settings.index_check_interval_seconds,
            name_source=companies.details_by_symbol,
        )
        hub = live_quote_hub.LiveQuoteHub()
        self._quote_reader = live_quote_reader.LiveQuoteReader(
            quote_gateway,
            hub,
            interval_seconds=explorer_settings.live_quote_interval_seconds,
        )
        snapshot_reader = quote_snapshot_reader.QuoteSnapshotReader(
            quote_gateway,
        )
        chain_builder = option_chain_builder.OptionChainBuilder(
            self._maintainer,
            snapshot_reader,
            self.time_source,
            explorer_settings.risk_free_rate,
        )
        universe = universe_service.UniverseService(
            self._maintainer,
            snapshot_reader,
            self.time_source,
        )
        self._chat_parts = self._build_chat()
        knowledge_parts = self._build_knowledge(client, companies, hub)
        screener_parts = self._build_screener(client, companies, hub)
        ubi_checker = health_checker.HealthChecker(
            client,
            self._tradingmachine.token_source,
            self.time_source,
        )
        password_authenticator = authenticator.Authenticator(
            explorer_settings.password_hash,
            self.time_source,
        )
        return self.create_web_application(
            password_authenticator,
            [
                ubi_checker,
                self._mongo,
                self._chroma,
            ],
            self._maintainer,
            client,
            hub,
            chain_builder,
            knowledge_parts,
            screener_parts,
            universe,
            self._chat_parts,
            with_lifespan=True,
        )

    def _build_chat(self) -> chat_routes.ChatParts:
        """Builds the chat assistant's stores, and its Claude client when an API key is set.

        Returns:
            chat_routes.ChatParts: The assistant's components.
        """
        explorer_settings = self.explorer_settings
        client = None
        if explorer_settings.assistant_configured():
            client = anthropic.AsyncAnthropic(
                api_key=explorer_settings.anthropic_api_key,
            )
        database = self._mongo.database()
        return chat_routes.ChatParts(
            client,
            conversation_repository.ConversationRepository(database),
            chat_usage_repository.ChatUsageRepository(database),
            explorer_settings,
        )

    def _build_screener(
        self,
        client: catalogue_gateway.CatalogueGateway,
        companies: company_repository.CompanyRepository,
        hub: live_quote_hub.LiveQuoteHub,
    ) -> screener_routes.ScreenerParts:
        """Builds the screener: its universe, figures job, service and daily scheduler.

        Args:
            client (catalogue_gateway.CatalogueGateway): Reads candles from UBI.
            companies (company_repository.CompanyRepository): Knows the index members and sectors.
            hub (live_quote_hub.LiveQuoteHub): Announces run progress to browsers.

        Returns:
            screener_routes.ScreenerParts: The components the screener routes use.
        """
        repository = screener_repository.ScreenerRepository(
            self._mongo.database()
        )
        universe = screener_universe.ScreenerUniverse(
            self._maintainer, companies
        )
        job = snapshot_job.ScreenerSnapshotJob(
            universe,
            client,
            repository,
            hub.broadcast_event,
            self.time_source,
        )
        catalogue = condition_catalogue.ConditionCatalogue()
        self._screener_scheduler = screener_scheduler.ScreenerScheduler(
            job,
            repository,
            self.time_source,
        )
        return screener_routes.ScreenerParts(
            universe,
            job,
            screener_service.ScreenerService(universe, repository, catalogue),
            catalogue,
            repository,
        )

    def _build_knowledge(
        self,
        client: catalogue_gateway.CatalogueGateway,
        companies: company_repository.CompanyRepository,
        hub: live_quote_hub.LiveQuoteHub,
    ) -> knowledge_routes.KnowledgeParts:
        """Builds the knowledge pipeline: the polite web client, the fetchers, storage, the job runner and the scheduler.

        Args:
            client (catalogue_gateway.CatalogueGateway): Reads broker attributes from UBI.
            companies (company_repository.CompanyRepository): Stores company documents.
            hub (live_quote_hub.LiveQuoteHub): Announces job progress to browsers.

        Returns:
            knowledge_routes.KnowledgeParts: The components the knowledge routes use.
        """
        explorer_settings = self.explorer_settings
        database = self._mongo.database()
        documents = document_repository.DocumentRepository(database)
        jobs = fetch_job_repository.FetchJobRepository(database)
        self._web_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                'User-Agent': _WEB_USER_AGENT,
            },
        )
        polite = polite_client.PoliteHttpClient(
            self._web_client,
            _ROBOTS_AGENT,
            explorer_settings.knowledge_host_interval_seconds,
        )
        yahoo = yahoo_fundamentals.YahooFundamentalsFetcher()
        fetchers = [
            nse_announcements.NseAnnouncementsFetcher(polite),
            yahoo,
            screener_in.ScreenerFetcher(polite),
            zaubacorp_directors.ZaubacorpDirectorsFetcher(polite),
            wikipedia.WikipediaFetcher(
                polite,
                explorer_settings.knowledge_contact,
            ),
            rss_news.RssNewsFetcher(polite),
            bing_news.BingNewsFetcher(polite),
            google_search.GoogleSearchFetcher(
                polite,
                explorer_settings.google_search_api_key,
                explorer_settings.google_search_engine_id,
            ),
        ]
        service = knowledge_service.KnowledgeService(
            companies,
            documents,
            vector_store.VectorStore(
                explorer_settings.chromadb_host,
                explorer_settings.chromadb_port,
            ),
            self.time_source,
        )
        runner = fetch_job_runner.FetchJobRunner(
            fetchers,
            service,
            jobs,
            hub.broadcast_event,
            self.time_source,
        )
        self._scheduler = knowledge_scheduler.KnowledgeScheduler(
            runner,
            companies,
            explorer_settings.knowledge_refresh_hours,
        )
        self._knowledge_parts = knowledge_routes.KnowledgeParts(
            company_resolver.CompanyResolver(
                self._maintainer, client, companies
            ),
            service,
            runner,
            listing_importer.ListingImporter(
                polite, companies, self.time_source
            ),
            companies,
            documents,
            jobs,
            self._maintainer.rebuild,
            geocoder=postcode_geocoder.PostcodeGeocoder(
                explorer_settings.data_directory / 'geonames',
            ),
            people_extractor=self._build_people_extractor(),
            sweep=headquarters_sweep.HeadquartersSweep(
                yahoo,
                service,
                companies,
                hub.broadcast_event,
                self.time_source,
                explorer_settings.knowledge_host_interval_seconds,
            ),
        )
        return self._knowledge_parts

    def _build_people_extractor(
        self,
    ) -> key_people_extractor.KeyPeopleExtractor | None:
        """Builds the reader of key people from uploaded documents, which shares the chat assistant's Claude client and daily limit.

        Returns:
            key_people_extractor.KeyPeopleExtractor | None: The reader, or None when no API key is set.
        """
        if self._chat_parts.client is None:
            return None
        return key_people_extractor.KeyPeopleExtractor(
            self._chat_parts.client,
            self._chat_parts.usage,
            self.explorer_settings,
            self.time_source,
        )

    def create_web_application(
        self,
        password_authenticator: authenticator.Authenticator,
        store_checkers: Sequence[status_routes.StoreChecker],
        maintainer: instrument_index_maintainer.InstrumentIndexMaintainer,
        client: catalogue_gateway.CatalogueGateway,
        hub: live_quote_hub.LiveQuoteHub,
        chain_builder: option_chain_builder.OptionChainBuilder,
        knowledge_parts: knowledge_routes.KnowledgeParts,
        screener_parts: screener_routes.ScreenerParts,
        universe: universe_service.UniverseService,
        chat_parts: chat_routes.ChatParts,
        with_lifespan: bool,
    ) -> fastapi.FastAPI:
        """Assembles the FastAPI application from ready components.

        Tests call this with test components and without the lifespan.

        Args:
            password_authenticator (authenticator.Authenticator): Checks the login password.
            store_checkers (Sequence[status_routes.StoreChecker]): Report whether UBI and each of the project's stores is reachable.
            maintainer (instrument_index_maintainer.InstrumentIndexMaintainer): Holds and refreshes the instrument index.
            client (catalogue_gateway.CatalogueGateway): Reads instruments, quotes and candles from UBI.
            hub (live_quote_hub.LiveQuoteHub): Delivers live quotes to browsers.
            chain_builder (option_chain_builder.OptionChainBuilder): Builds option chains and volatility surfaces.
            knowledge_parts (knowledge_routes.KnowledgeParts): The knowledge pipeline's components.
            screener_parts (screener_routes.ScreenerParts): The screener's components.
            universe (universe_service.UniverseService): Lays out the 3D universe map.
            chat_parts (chat_routes.ChatParts): The chat assistant's components.
            with_lifespan (bool): Whether start-up should open and refresh the index and start the quote reader, and shutdown close everything.

        Returns:
            fastapi.FastAPI: The web application.
        """
        lifespan = None
        if with_lifespan:
            lifespan = self._lifespan
        web_application = fastapi.FastAPI(
            title='Instruments Explorer',
            docs_url=None,
            redoc_url=None,
            openapi_url=None,
            lifespan=lifespan,
        )
        web_application.add_middleware(
            starlette.middleware.gzip.GZipMiddleware,
            minimum_size=2000,
        )
        web_application.add_middleware(
            starlette.middleware.sessions.SessionMiddleware,
            secret_key=self.explorer_settings.session_secret,
            session_cookie=_SESSION_COOKIE,
            max_age=self.explorer_settings.session_max_age_seconds,
            same_site='strict',
            https_only=False,
        )
        guard = session_guard.SessionGuard()
        authentication = auth_routes.AuthRoutes(
            password_authenticator,
            guard,
            self.time_source,
        )
        status = status_routes.StatusRoutes(
            self.explorer_settings,
            store_checkers,
            maintainer,
            guard,
        )
        instruments = instrument_routes.InstrumentRoutes(
            maintainer,
            client,
            guard,
        )
        charts = chart_routes.ChartRoutes(
            client,
            indicator_catalogue.IndicatorCatalogue(),
            guard,
        )
        derivatives = derivative_routes.DerivativeRoutes(chain_builder, guard)
        knowledge = knowledge_routes.KnowledgeRoutes(knowledge_parts, guard)
        earth = earth_routes.EarthRoutes(
            knowledge_parts,
            knowledge,
            maintainer,
            guard,
        )
        screener = screener_routes.ScreenerRoutes(screener_parts, guard)
        universe_map = universe_routes.UniverseRoutes(universe, guard)
        services = assistant_services.AssistantServices(
            instruments,
            charts,
            derivatives,
            knowledge,
            screener,
        )
        chat = chat_routes.ChatRoutes(
            chat_parts,
            tool_box.ToolBox(services),
            guard,
            self.time_source,
        )
        live = live_routes.LiveRoutes(
            hub,
            guard,
            websocket_origin_checker.WebsocketOriginChecker(),
            self.time_source,
        )
        frontend = frontend_routes.FrontendRoutes(
            self.explorer_settings.frontend_directory,
        )
        web_application.include_router(authentication.router)
        web_application.include_router(status.router)
        web_application.include_router(instruments.router)
        web_application.include_router(charts.router)
        web_application.include_router(derivatives.router)
        web_application.include_router(knowledge.router)
        web_application.include_router(earth.router)
        web_application.include_router(screener.router)
        web_application.include_router(universe_map.router)
        web_application.include_router(chat.router)
        web_application.include_router(live.router)
        web_application.include_router(frontend.router)
        return web_application

    @contextlib.asynccontextmanager
    async def _lifespan(
        self,
        web_application: fastapi.FastAPI,
    ) -> AsyncIterator[None]:
        """Runs the index maintainer and the quote reader while the server runs, and closes everything when it stops.

        This is a context manager decorator used as FastAPI's lifespan.

        Args:
            web_application (fastapi.FastAPI): The application being run.

        Yields:
            None: Control returns to the server while the application runs.
        """
        del web_application
        await asyncio.to_thread(self._maintainer.open_newest_existing)
        tasks = [
            asyncio.create_task(self._prepare_knowledge()),
            asyncio.create_task(self._maintainer.run()),
            asyncio.create_task(self._quote_reader.run()),
            asyncio.create_task(self._knowledge_parts.runner.run()),
            asyncio.create_task(self._scheduler.run()),
            asyncio.create_task(self._screener_scheduler.run()),
        ]
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            for task in tasks:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            if self._maintainer.current_index is not None:
                self._maintainer.current_index.close()
            await self._web_client.aclose()
            await asyncio.to_thread(self._tradingmachine.close)
            await self._mongo.close()
            await self._chroma.close()
            if self._chat_parts.client is not None:
                await self._chat_parts.client.close()

    async def _prepare_knowledge(self) -> None:
        """Creates the MongoDB indexes, and imports NSE's equity list and the Nifty Total Market industries the first time the application starts."""
        parts = self._knowledge_parts
        try:
            await parts.companies.ensure_indexes()
            await parts.documents.ensure_indexes()
            await self._chat_parts.conversations.ensure_indexes()
            counts = await parts.companies.counts()
            changed = False
            if counts['listed'] == 0:
                imported = await parts.importer.import_nse()
                _LOGGER.info('Imported %d companies from NSE.', imported)
                changed = True
            if counts['classified'] == 0:
                classified = await parts.importer.import_sectors()
                _LOGGER.info(
                    'Imported industries for %d companies.', classified
                )
                changed = True
            if changed:
                await parts.after_listing_import()
        except Exception as error:  # noqa: BLE001
            _LOGGER.warning('Preparing company knowledge failed: %s', error)
