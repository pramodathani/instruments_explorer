"""Builds every component of instruments_explorer and runs the web server.

Typical usage example:

  Application().run()
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Sequence

import fastapi
import httpx
import starlette.middleware.sessions
import uvicorn

from instruments_explorer.configuration import settings
from instruments_explorer.configuration import (
    unified_broker_interface_configuration,
)
from instruments_explorer.instruments import instrument_index_builder
from instruments_explorer.instruments import instrument_index_maintainer
from instruments_explorer.market import live_quote_hub
from instruments_explorer.market import live_quote_reader
from instruments_explorer.routes import auth_routes
from instruments_explorer.routes import frontend_routes
from instruments_explorer.routes import instrument_routes
from instruments_explorer.routes import live_routes
from instruments_explorer.routes import status_routes
from instruments_explorer.security import authenticator
from instruments_explorer.security import session_guard
from instruments_explorer.security import websocket_origin_checker
from instruments_explorer.storage import chroma_connection
from instruments_explorer.storage import mongo_connection
from instruments_explorer.unified_broker_interface import access_token_provider
from instruments_explorer.unified_broker_interface import health_checker
from instruments_explorer.unified_broker_interface import mongo_reader
from instruments_explorer.unified_broker_interface import redis_reader
from instruments_explorer.unified_broker_interface import rest_client
from instruments_explorer.utilities import clock

_SESSION_COOKIE = 'instruments_explorer_session'


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
        self._http_client = None
        self._redis_reader = None
        self._mongo_reader = None
        self._maintainer = None
        self._quote_reader = None

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
        timeout = explorer_settings.ubi_request_timeout_seconds
        self._redis_reader = redis_reader.RedisReader.from_configuration(
            ubi_configuration,
            timeout,
        )
        self._mongo_reader = mongo_reader.MongoReader.from_configuration(
            ubi_configuration,
            timeout,
        )
        self._http_client = httpx.AsyncClient(
            base_url=ubi_configuration.rest_api_base_url,
            timeout=timeout,
        )
        token_provider = access_token_provider.AccessTokenProvider(
            self._http_client,
            self._redis_reader,
            self._mongo_reader,
            self.time_source,
            may_connect=explorer_settings.ubi_may_connect,
            connect_cooldown_seconds=explorer_settings.ubi_connect_cooldown_seconds,
        )
        client = rest_client.UnifiedBrokerInterfaceClient(
            self._http_client,
            token_provider,
        )
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
        )
        hub = live_quote_hub.LiveQuoteHub()
        self._quote_reader = live_quote_reader.LiveQuoteReader(
            self._redis_reader,
            hub,
            interval_seconds=explorer_settings.live_quote_interval_seconds,
        )
        ubi_checker = health_checker.HealthChecker(
            client,
            token_provider,
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
            with_lifespan=True,
        )

    def create_web_application(
        self,
        password_authenticator: authenticator.Authenticator,
        store_checkers: Sequence[status_routes.StoreChecker],
        maintainer: instrument_index_maintainer.InstrumentIndexMaintainer,
        client: rest_client.UnifiedBrokerInterfaceClient,
        hub: live_quote_hub.LiveQuoteHub,
        with_lifespan: bool,
    ) -> fastapi.FastAPI:
        """Assembles the FastAPI application from ready components.

        Tests call this with test components and without the lifespan.

        Args:
            password_authenticator (authenticator.Authenticator): Checks the login password.
            store_checkers (Sequence[status_routes.StoreChecker]): Report whether UBI and each of the project's stores is reachable.
            maintainer (instrument_index_maintainer.InstrumentIndexMaintainer): Holds and refreshes the instrument index.
            client (rest_client.UnifiedBrokerInterfaceClient): Reads instruments and quotes from UBI.
            hub (live_quote_hub.LiveQuoteHub): Delivers live quotes to browsers.
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
            asyncio.create_task(self._maintainer.run()),
            asyncio.create_task(self._quote_reader.run()),
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
            await self._http_client.aclose()
            await self._redis_reader.close()
            await asyncio.to_thread(self._mongo_reader.close)
            await self._mongo.close()
            await self._chroma.close()
