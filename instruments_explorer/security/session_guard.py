"""FastAPI dependencies that protect routes with the login session.

Typical usage example:

  guard = SessionGuard()
  router.add_api_route(
      '/api/status',
      handler,
      dependencies=[
          fastapi.Depends(guard.require_session),
      ],
  )
"""

import fastapi
import starlette.requests

REQUESTED_WITH_HEADER = 'X-Requested-With'
REQUESTED_WITH_VALUE = 'instruments-explorer'
AUTHENTICATED_KEY = 'authenticated'


class SessionGuard:
    """Checks the signed session cookie and the header that marks instruments_explorer's own requests."""

    def require_session(self, request: fastapi.Request) -> None:
        """Rejects a request without a logged-in session.

        Args:
            request (fastapi.Request): The incoming request.

        Raises:
            fastapi.HTTPException: 401 when the session is not logged in.
        """
        if not self.is_logged_in(request):
            raise fastapi.HTTPException(
                status_code=401,
                detail='Login required.',
            )

    def require_app_header(self, request: fastapi.Request) -> None:
        """Rejects a state-changing request that did not come from instruments_explorer's own script.

        Args:
            request (fastapi.Request): The incoming request.

        Raises:
            fastapi.HTTPException: 403 when the header is missing or wrong.
        """
        header_value = request.headers.get(REQUESTED_WITH_HEADER)
        if header_value != REQUESTED_WITH_VALUE:
            raise fastapi.HTTPException(
                status_code=403,
                detail=f'Missing {REQUESTED_WITH_HEADER} header.',
            )

    def log_in(self, request: fastapi.Request, now: float) -> None:
        """Marks the request's session as logged in.

        Args:
            request (fastapi.Request): The login request.
            now (float): The login time, in epoch seconds.
        """
        request.session.clear()
        request.session[AUTHENTICATED_KEY] = True
        request.session['logged_in_at'] = now

    def log_out(self, request: fastapi.Request) -> None:
        """Clears the request's session.

        Args:
            request (fastapi.Request): The logout request.
        """
        request.session.clear()

    def is_logged_in(self, request: starlette.requests.HTTPConnection) -> bool:
        """Checks whether a request's or WebSocket's session is logged in.

        Args:
            request (starlette.requests.HTTPConnection): The incoming request or WebSocket.

        Returns:
            bool: True when logged in.
        """
        return request.session.get(AUTHENTICATED_KEY) is True
