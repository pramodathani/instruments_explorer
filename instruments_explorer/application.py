"""Builds every component of instruments_explorer and runs the web server.

Typical usage example:

  Application().run()
"""

import contextlib
import logging
from collections.abc import AsyncIterator, Sequence

import fastapi
import starlette.middleware.sessions
import uvicorn

from instruments_explorer.configuration import settings
from instruments_explorer.routes import auth_routes
from instruments_explorer.routes import frontend_routes
from instruments_explorer.routes import status_routes
from instruments_explorer.security import authenticator
from instruments_explorer.security import session_guard
from instruments_explorer.storage import chroma_connection
from instruments_explorer.storage import mongo_connection
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

    def run(self) -> None:
        """Builds the application and serves it until stopped.

        Raises:
            ValueError: The password hash or session secret is missing.
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
            fastapi.FastAPI: The web application, whose shutdown closes the store connections.

        Raises:
            ValueError: The password hash or session secret is missing.
        """
        self.explorer_settings.require_security_values()
        self._mongo = mongo_connection.MongoConnection(self.explorer_settings)
        self._chroma = chroma_connection.ChromaConnection(
            self.explorer_settings
        )
        password_authenticator = authenticator.Authenticator(
            self.explorer_settings.password_hash,
            self.time_source,
        )
        return self.create_web_application(
            password_authenticator,
            [
                self._mongo,
                self._chroma,
            ],
            with_lifespan=True,
        )

    def create_web_application(
        self,
        password_authenticator: authenticator.Authenticator,
        store_checkers: Sequence[status_routes.StoreChecker],
        with_lifespan: bool,
    ) -> fastapi.FastAPI:
        """Assembles the FastAPI application from ready components.

        Tests call this with test components and without the lifespan.

        Args:
            password_authenticator (authenticator.Authenticator): Checks the login password.
            store_checkers (Sequence[status_routes.StoreChecker]): Report whether each of the project's stores is reachable.
            with_lifespan (bool): Whether shutdown should close the store connections.

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
            guard,
        )
        frontend = frontend_routes.FrontendRoutes(
            self.explorer_settings.frontend_directory,
        )
        web_application.include_router(authentication.router)
        web_application.include_router(status.router)
        web_application.include_router(frontend.router)
        return web_application

    @contextlib.asynccontextmanager
    async def _lifespan(
        self,
        web_application: fastapi.FastAPI,
    ) -> AsyncIterator[None]:
        """Closes the store connections when the server stops.

        This is a context manager decorator used as FastAPI's lifespan.

        Args:
            web_application (fastapi.FastAPI): The application being run.

        Yields:
            None: Control returns to the server while the application runs.
        """
        del web_application
        try:
            yield
        finally:
            await self._mongo.close()
            await self._chroma.close()
