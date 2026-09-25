"""Login, logout and session status routes.

Typical usage example:

  web_application.include_router(
      AuthRoutes(password_authenticator, guard, time_source).router
  )
"""

import fastapi
import pydantic

from instruments_explorer.security import authenticator
from instruments_explorer.security import session_guard
from instruments_explorer.utilities import clock


class LoginRequest(pydantic.BaseModel):
    """The body of a login request.

    Attributes:
        password: The login password.
    """

    password: str


class AuthRoutes:
    """The /api/auth routes.

    Attributes:
        router: The FastAPI router holding the routes.
    """

    def __init__(
        self,
        password_authenticator: authenticator.Authenticator,
        guard: session_guard.SessionGuard,
        time_source: clock.SystemClock,
    ):
        """Creates the routes.

        Args:
            password_authenticator (authenticator.Authenticator): Checks passwords and lockouts.
            guard (session_guard.SessionGuard): Reads and writes the session.
            time_source (clock.SystemClock): The source of the current time.
        """
        self.password_authenticator = password_authenticator
        self.guard = guard
        self.time_source = time_source
        self.router = fastapi.APIRouter()
        self.router.add_api_route(
            '/api/auth/login',
            self.log_in,
            methods=[
                'POST',
            ],
            dependencies=[
                fastapi.Depends(guard.require_app_header),
            ],
        )
        self.router.add_api_route(
            '/api/auth/logout',
            self.log_out,
            methods=[
                'POST',
            ],
            dependencies=[
                fastapi.Depends(guard.require_app_header),
            ],
        )
        self.router.add_api_route(
            '/api/auth/session',
            self.session,
            methods=[
                'GET',
            ],
        )

    def log_in(
        self,
        request: fastapi.Request,
        body: LoginRequest,
    ) -> dict[str, bool]:
        """Checks the password and starts a session.

        Args:
            request (fastapi.Request): The request, for its address and session.
            body (LoginRequest): The submitted password.

        Returns:
            dict[str, bool]: {"authenticated": True}.

        Raises:
            fastapi.HTTPException: 429 when the address is locked out, 401 when the password is wrong.
        """
        address = self._address(request)
        if self.password_authenticator.is_locked_out(address):
            raise fastapi.HTTPException(
                status_code=429,
                detail='Too many wrong passwords; wait five minutes.',
            )
        if not self.password_authenticator.verify(address, body.password):
            raise fastapi.HTTPException(
                status_code=401,
                detail='Wrong password.',
            )
        self.guard.log_in(request, self.time_source.now())
        return {
            'authenticated': True,
        }

    def log_out(self, request: fastapi.Request) -> dict[str, bool]:
        """Ends the session.

        Args:
            request (fastapi.Request): The request, for its session.

        Returns:
            dict[str, bool]: {"authenticated": False}.
        """
        self.guard.log_out(request)
        return {
            'authenticated': False,
        }

    def session(self, request: fastapi.Request) -> dict[str, bool]:
        """Reports whether the browser is logged in.

        Args:
            request (fastapi.Request): The request, for its session.

        Returns:
            dict[str, bool]: {"authenticated": True or False}.
        """
        return {
            'authenticated': self.guard.is_logged_in(request),
        }

    def _address(self, request: fastapi.Request) -> str:
        """Finds the client's network address.

        Args:
            request (fastapi.Request): The request.

        Returns:
            str: The address, or "unknown".
        """
        if request.client is None:
            return 'unknown'
        return request.client.host
