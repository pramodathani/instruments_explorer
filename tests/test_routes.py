"""Tests for the web routes, assembled with test components."""

from pathlib import Path

import argon2
import fastapi.testclient

from instruments_explorer import application
from instruments_explorer.configuration import settings
from instruments_explorer.security import authenticator
from tests import fakes

_PASSWORD = 'correct horse battery'
_HASH = argon2.PasswordHasher(
    time_cost=1,
    memory_cost=8,
    parallelism=1,
).hash(_PASSWORD)
_HEADERS = {
    'X-Requested-With': 'instruments-explorer',
}


class TestRoutes:
    """Tests for the routes the application serves."""

    def _client(
        self,
        frontend_directory: Path,
        api_key: str = '',
    ) -> fastapi.testclient.TestClient:
        """Builds a test client over the application with prepared stores.

        Args:
            frontend_directory (Path): Where the built front end is looked for.
            api_key (str): The Claude API key setting.

        Returns:
            fastapi.testclient.TestClient: The client.
        """
        explorer_settings = settings.Settings(
            _env_file=None,
            password_hash=_HASH,
            session_secret='test secret',
            frontend_directory=frontend_directory,
            anthropic_api_key=api_key,
        )
        explorer = application.Application(explorer_settings)
        time_source = fakes.FixedClock(1_000_000.0)
        web_application = explorer.create_web_application(
            authenticator.Authenticator(_HASH, time_source),
            [
                fakes.FakeStoreChecker('MongoDB', True),
                fakes.FakeStoreChecker('ChromaDB', False),
            ],
            with_lifespan=False,
        )
        return fastapi.testclient.TestClient(web_application)

    def _log_in(self, client: fastapi.testclient.TestClient) -> None:
        """Logs the client in.

        Args:
            client (fastapi.testclient.TestClient): The client to log in.
        """
        response = client.post(
            '/api/auth/login',
            json={
                'password': _PASSWORD,
            },
            headers=_HEADERS,
        )
        assert response.status_code == 200

    def test_login_and_logout(self, tmp_path: Path) -> None:
        """Checks that a login starts a session and a logout ends it.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        client = self._client(tmp_path)
        assert client.get('/api/auth/session').json() == {
            'authenticated': False,
        }
        self._log_in(client)
        assert client.get('/api/auth/session').json() == {
            'authenticated': True,
        }
        client.post('/api/auth/logout', headers=_HEADERS)
        assert client.get('/api/auth/session').json() == {
            'authenticated': False,
        }

    def test_login_needs_the_application_header(self, tmp_path: Path) -> None:
        """Checks that a login without the header is refused.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        client = self._client(tmp_path)
        response = client.post(
            '/api/auth/login',
            json={
                'password': _PASSWORD,
            },
        )
        assert response.status_code == 403

    def test_wrong_password_is_refused(self, tmp_path: Path) -> None:
        """Checks that a wrong password gets 401.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        client = self._client(tmp_path)
        response = client.post(
            '/api/auth/login',
            json={
                'password': 'wrong',
            },
            headers=_HEADERS,
        )
        assert response.status_code == 401

    def test_status_needs_a_session(self, tmp_path: Path) -> None:
        """Checks that the status route refuses a logged-out browser.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        client = self._client(tmp_path)
        assert client.get('/api/status').status_code == 401

    def test_status_reports_stores_and_assistant(self, tmp_path: Path) -> None:
        """Checks the status report's stores and assistant sections.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        client = self._client(tmp_path, api_key='key')
        self._log_in(client)
        body = client.get('/api/status').json()
        reachable_by_name = {}
        for store in body['stores']:
            reachable_by_name[store['name']] = store['reachable']
        assert reachable_by_name == {
            'MongoDB': True,
            'ChromaDB': False,
        }
        assert body['assistant'] == {
            'configured': True,
            'model': 'claude-opus-5-5',
        }

    def test_unbuilt_frontend_gives_503(self, tmp_path: Path) -> None:
        """Checks the page shown before the front end is built.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        client = self._client(tmp_path)
        response = client.get('/explore')
        assert response.status_code == 503
        assert 'npm run build' in response.text

    def test_frontend_falls_back_to_index(self, tmp_path: Path) -> None:
        """Checks that a client-side route is answered with index.html.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        (tmp_path / 'index.html').write_text('<p>app</p>')
        client = self._client(tmp_path)
        response = client.get('/instrument/abc')
        assert response.status_code == 200
        assert response.text == '<p>app</p>'

    def test_unknown_api_path_gives_404(self, tmp_path: Path) -> None:
        """Checks that an unknown /api path is not answered with the app.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        (tmp_path / 'index.html').write_text('<p>app</p>')
        client = self._client(tmp_path)
        assert client.get('/api/nothing').status_code == 404
