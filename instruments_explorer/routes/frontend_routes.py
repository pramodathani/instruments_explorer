"""Serves the built React application, falling back to index.html for client-side routes.

Typical usage example:

  web_application.include_router(
      FrontendRoutes(Path('frontend/dist')).router
  )
"""

from pathlib import Path

import fastapi
import fastapi.responses

_NOT_BUILT_PAGE = '<!doctype html><title>Instruments Explorer</title><p>The front end has not been built. Run <code>npm run build</code> in <code>frontend/</code>.</p>'


class FrontendRoutes:
    """The catch-all route for the single-page application.

    Attributes:
        frontend_directory: The Vite build output directory.
        router: The FastAPI router holding the route.
    """

    def __init__(self, frontend_directory: Path):
        """Creates the route.

        Args:
            frontend_directory (Path): The Vite build output directory.
        """
        self.frontend_directory = frontend_directory.resolve()
        self.router = fastapi.APIRouter()
        self.router.add_api_route(
            '/{path:path}',
            self.serve,
            methods=[
                'GET',
            ],
            include_in_schema=False,
        )

    def serve(self, path: str) -> fastapi.responses.Response:
        """Serves a built file, or index.html for any other page address.

        Args:
            path (str): The requested path without the leading slash.

        Returns:
            fastapi.responses.Response: The file, index.html, or a page explaining that the front end is not built.

        Raises:
            fastapi.HTTPException: 404 for an unknown /api path.
        """
        if path == 'api' or path.startswith('api/'):
            raise fastapi.HTTPException(
                status_code=404,
                detail='Not found.',
            )
        index = self.frontend_directory / 'index.html'
        if not index.is_file():
            return fastapi.responses.HTMLResponse(
                _NOT_BUILT_PAGE,
                status_code=503,
            )
        if path:
            candidate = (self.frontend_directory / path).resolve()
            inside = candidate.is_relative_to(self.frontend_directory)
            if candidate.is_file() and inside:
                return fastapi.responses.FileResponse(
                    candidate,
                    headers=self._cache_headers(path),
                )
        return fastapi.responses.FileResponse(
            index,
            headers={
                'Cache-Control': 'no-cache',
            },
        )

    def _cache_headers(self, path: str) -> dict[str, str]:
        """Chooses caching for a built file.

        Args:
            path (str): The requested path.

        Returns:
            dict[str, str]: The Cache-Control header.
        """
        if path.startswith('assets/'):
            return {
                'Cache-Control': 'public, max-age=31536000, immutable',
            }
        return {
            'Cache-Control': 'no-cache',
        }
