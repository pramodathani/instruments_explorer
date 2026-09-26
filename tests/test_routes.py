"""Tests for the web routes, assembled with test components."""

import asyncio
from pathlib import Path

import argon2
import fastapi.testclient
import pytest
import starlette.websockets

from instruments_explorer import application
from instruments_explorer.configuration import settings
from instruments_explorer.derivatives import option_chain_builder
from instruments_explorer.instruments import instrument_index_builder
from instruments_explorer.instruments import instrument_index_maintainer
from instruments_explorer.market import live_quote_hub
from instruments_explorer.security import authenticator
from instruments_explorer.unified_broker_interface import exceptions
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


class RouteParts:
    """The test components behind one test client.

    Attributes:
        client: The test HTTP client.
        catalogue_client: The stand-in for UBI's REST client.
        hub: The live quote hub.
        maintainer: The index maintainer.
        snapshot_reader: The stand-in for the live quote snapshot reader.
    """

    def __init__(
        self,
        frontend_directory: Path,
        index_directory: Path,
        api_key: str = '',
        build_index: bool = True,
    ):
        """Builds the application with test components.

        Args:
            frontend_directory (Path): Where the built front end is looked for.
            index_directory (Path): Where the instrument index is built.
            api_key (str): The Claude API key setting.
            build_index (bool): Whether to build the index before serving, or leave it not ready.
        """
        explorer_settings = settings.Settings(
            _env_file=None,
            password_hash=_HASH,
            session_secret='test secret',
            frontend_directory=frontend_directory,
            anthropic_api_key=api_key,
        )
        explorer = application.Application(explorer_settings)
        time_source = fakes.FixedClock(fakes.TODAY_EPOCH)
        self.catalogue_client = fakes.FakeCatalogueClient(
            fakes.CatalogueMaker().catalogue()
        )
        self.maintainer = instrument_index_maintainer.InstrumentIndexMaintainer(
            self.catalogue_client,
            instrument_index_builder.InstrumentIndexBuilder(
                self.catalogue_client,
                index_directory,
                time_source,
            ),
            time_source,
        )
        if build_index:
            asyncio.run(self.maintainer.refresh())
        self.hub = live_quote_hub.LiveQuoteHub()
        self.snapshot_reader = fakes.FakeSnapshotReader()
        chain_builder = option_chain_builder.OptionChainBuilder(
            self.maintainer,
            self.snapshot_reader,
            time_source,
            0.065,
        )
        web_application = explorer.create_web_application(
            authenticator.Authenticator(_HASH, time_source),
            [
                fakes.FakeStoreChecker('MongoDB', True),
                fakes.FakeStoreChecker('ChromaDB', False),
            ],
            self.maintainer,
            self.catalogue_client,
            self.hub,
            chain_builder,
            with_lifespan=False,
        )
        self.client = fastapi.testclient.TestClient(web_application)

    def log_in(self) -> None:
        """Logs the client in."""
        response = self.client.post(
            '/api/auth/login',
            json={
                'password': _PASSWORD,
            },
            headers=_HEADERS,
        )
        assert response.status_code == 200


class TestAuthenticationAndStatus:
    """Tests for login, the status route and the frontend fallback."""

    def test_login_and_logout(self, tmp_path: Path) -> None:
        """Checks that a login starts a session and a logout ends it.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        client = parts.client
        assert client.get('/api/auth/session').json() == {
            'authenticated': False,
        }
        parts.log_in()
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
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        response = parts.client.post(
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
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        response = parts.client.post(
            '/api/auth/login',
            json={
                'password': 'wrong',
            },
            headers=_HEADERS,
        )
        assert response.status_code == 401

    def test_api_routes_need_a_session(self, tmp_path: Path) -> None:
        """Checks that data routes refuse a logged-out browser.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        for path in [
            '/api/status',
            '/api/instruments/search',
            f'/api/instruments/{fakes.NIFTY_ID}',
        ]:
            assert parts.client.get(path).status_code == 401

    def test_status_reports_stores_index_and_assistant(
        self,
        tmp_path: Path,
    ) -> None:
        """Checks the status report's sections.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index', 'key')
        parts.log_in()
        body = parts.client.get('/api/status').json()
        reachable_by_name = {}
        for store in body['stores']:
            reachable_by_name[store['name']] = store['reachable']
        assert reachable_by_name == {
            'MongoDB': True,
            'ChromaDB': False,
        }
        assert body['index']['state'] == 'ready'
        assert body['index']['instrument_count'] == 10
        assert body['assistant'] == {
            'configured': True,
            'model': 'claude-opus-5-5',
        }

    def test_unbuilt_frontend_gives_503(self, tmp_path: Path) -> None:
        """Checks the page shown before the front end is built.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        response = parts.client.get('/explore')
        assert response.status_code == 503
        assert 'npm run build' in response.text

    def test_frontend_falls_back_to_index(self, tmp_path: Path) -> None:
        """Checks that a client-side route is answered with index.html.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        (tmp_path / 'index.html').write_text('<p>app</p>')
        parts = RouteParts(tmp_path, tmp_path / 'index')
        response = parts.client.get('/instrument/abc')
        assert response.status_code == 200
        assert response.text == '<p>app</p>'

    def test_unknown_api_path_gives_404(self, tmp_path: Path) -> None:
        """Checks that an unknown /api path is not answered with the app.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        (tmp_path / 'index.html').write_text('<p>app</p>')
        parts = RouteParts(tmp_path, tmp_path / 'index')
        parts.log_in()
        assert parts.client.get('/api/nothing/here').status_code == 404


class TestInstrumentRoutes:
    """Tests for the /api/instruments routes."""

    def test_search_with_repeated_filters(self, tmp_path: Path) -> None:
        """Checks text search combined with a repeated filter.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        parts.log_in()
        response = parts.client.get(
            '/api/instruments/search?q=nifty&shape=option&shape=future&sort=name'
        )
        body = response.json()
        assert response.status_code == 200
        assert body['total'] == 4
        assert body['mapping_date'] == '2026-09-25'
        assert set(body['facets']) == {
            'exchange',
            'asset_class',
            'shape',
            'segment',
            'option_type',
            'expiry_month',
        }

    def test_search_refuses_a_bad_sort(self, tmp_path: Path) -> None:
        """Checks that an unknown sort order gets 400.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        parts.log_in()
        response = parts.client.get('/api/instruments/search?sort=random')
        assert response.status_code == 400

    def test_search_before_the_index_is_ready(self, tmp_path: Path) -> None:
        """Checks that a search gets 503 while the index is not built.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(
            tmp_path / 'dist',
            tmp_path / 'index',
            build_index=False,
        )
        parts.log_in()
        response = parts.client.get('/api/instruments/search?q=nifty')
        assert response.status_code == 503
        assert 'not ready' in response.json()['detail']

    def test_instrument_merges_ubi_details(self, tmp_path: Path) -> None:
        """Checks the index record, details and first-found attributes.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        parts.catalogue_client.details_by_id[fakes.RELIANCE_NSE_ID] = {
            'lot_size': 1,
            'tick_size': '0.1',
        }
        parts.catalogue_client.additional_by_id[fakes.RELIANCE_NSE_ID] = {
            'attribute_names': [
                'isin',
                'display_name',
            ],
            'carried_by': [
                {
                    'broker': 'dhan',
                    'isin': None,
                    'display_name': 'Reliance Industries',
                },
                {
                    'broker': 'zerodha',
                    'isin': 'INE002A01018',
                    'display_name': 'RELIANCE INDUSTRIES',
                },
            ],
        }
        parts.log_in()
        body = parts.client.get(
            f'/api/instruments/{fakes.RELIANCE_NSE_ID}'
        ).json()
        assert body['instrument']['display_name'] == 'RELIANCE'
        assert body['details']['lot_size'] == 1
        assert body['attributes'] == {
            'isin': 'INE002A01018',
            'display_name': 'Reliance Industries',
        }
        assert body['ubi_error'] is None

    def test_instrument_survives_ubi_being_down(self, tmp_path: Path) -> None:
        """Checks that the index record is still returned when UBI fails.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        parts.catalogue_client.failure = exceptions.UnreachableError(
            'UBI is down in this test.'
        )
        parts.log_in()
        body = parts.client.get(f'/api/instruments/{fakes.NIFTY_ID}').json()
        assert body['instrument']['display_name'] == 'NIFTY'
        assert body['details'] is None
        assert body['ubi_error'] == 'UBI is down in this test.'

    def test_unknown_instrument_gives_404(self, tmp_path: Path) -> None:
        """Checks that an id neither the index nor UBI knows gets 404.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        parts.log_in()
        response = parts.client.get('/api/instruments/nobody')
        assert response.status_code == 404

    def test_quote_is_encoded(self, tmp_path: Path) -> None:
        """Checks the quote route's encoding and source.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        parts.catalogue_client.quotes_by_id[fakes.NIFTY_ID] = {
            'instrument_id': fakes.NIFTY_ID,
            'last_price': 25100.0,
            'previous_close': 25000.0,
            'ohlc': {
                'open': 25010.0,
                'high': 25150.0,
                'low': 24990.0,
            },
            'source': 'broker',
        }
        parts.log_in()
        body = parts.client.get(
            f'/api/instruments/{fakes.NIFTY_ID}/quote'
        ).json()
        assert body['change'] == 100.0
        assert body['high'] == 25150.0
        assert body['source'] == 'broker'

    @pytest.mark.parametrize(
        (
            'failure',
            'status_code',
        ),
        [
            (
                exceptions.UnreachableError('down'),
                503,
            ),
            (
                exceptions.NotFoundError('missing'),
                404,
            ),
            (
                exceptions.BrokerError('no broker'),
                502,
            ),
        ],
    )
    def test_quote_failures(
        self,
        tmp_path: Path,
        failure: exceptions.UnifiedBrokerInterfaceError,
        status_code: int,
    ) -> None:
        """Checks the status code for each kind of UBI failure.

        Args:
            tmp_path (Path): A temporary directory from pytest.
            failure (exceptions.UnifiedBrokerInterfaceError): The failure UBI raises.
            status_code (int): The status code expected.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        parts.catalogue_client.failure = failure
        parts.log_in()
        response = parts.client.get(f'/api/instruments/{fakes.NIFTY_ID}/quote')
        assert response.status_code == status_code


class TestLiveRoute:
    """Tests for the /api/live WebSocket."""

    def test_subscribed_quote_arrives(self, tmp_path: Path) -> None:
        """Checks that a subscribed instrument's quote reaches the browser.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        parts.log_in()
        with parts.client.websocket_connect(
            '/api/live',
            headers={
                'origin': 'http://testserver',
            },
        ) as websocket:
            websocket.send_json(
                {
                    'type': 'subscribe',
                    'instrument_ids': [
                        fakes.NIFTY_ID,
                    ],
                }
            )
            websocket.send_json(
                {
                    'type': 'ping',
                }
            )
            assert websocket.receive_json()['type'] == 'pong'
            parts.hub.deliver(
                {
                    'instrument_id': fakes.NIFTY_ID,
                    'last_price': 25100.0,
                    'previous_close': 25000.0,
                    'received_at': 1.0,
                },
                'live',
            )
            message = websocket.receive_json()
        assert message['type'] == 'quotes'
        assert message['quotes'][0]['last_price'] == 25100.0

    def test_other_origin_is_refused(self, tmp_path: Path) -> None:
        """Checks that a page from another site cannot open the feed.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        parts.log_in()
        with (
            pytest.raises(starlette.websockets.WebSocketDisconnect),
            parts.client.websocket_connect(
                '/api/live',
                headers={
                    'origin': 'http://elsewhere.example',
                },
            ) as websocket,
        ):
            websocket.receive_json()

    def test_logged_out_browser_is_refused(self, tmp_path: Path) -> None:
        """Checks that the feed needs a session.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        with (
            pytest.raises(starlette.websockets.WebSocketDisconnect),
            parts.client.websocket_connect(
                '/api/live',
                headers={
                    'origin': 'http://testserver',
                },
            ) as websocket,
        ):
            websocket.receive_json()


class TestChartRoutes:
    """Tests for the chart and indicator catalogue routes."""

    def test_indicator_catalogue(self, tmp_path: Path) -> None:
        """Checks that the catalogue lists the indicators.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        parts.log_in()
        keys = []
        for description in parts.client.get('/api/indicators').json():
            keys.append(description['key'])
        assert 'rsi' in keys
        assert 'macd' in keys

    def test_chart_with_indicators(self, tmp_path: Path) -> None:
        """Checks candles, indicators, errors and the request passed to UBI.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        parts.catalogue_client.prices_by_id[fakes.NIFTY_ID] = (
            fakes.PricesMaker().document(100)
        )
        parts.log_in()
        response = parts.client.get(
            f'/api/instruments/{fakes.NIFTY_ID}/chart?interval=day&days=365&indicator=sma:20&indicator=macd&indicator=bogus'
        )
        body = response.json()
        assert response.status_code == 200
        assert len(body['candles']) == 100
        titles = []
        for result in body['indicators']:
            titles.append(result['title'])
        assert titles == [
            'SMA 20',
            'MACD 12, 26, 9',
        ]
        assert body['errors'] == [
            "Unknown indicator: 'bogus'",
        ]
        assert body['has_volume'] is True
        assert parts.catalogue_client.price_requests == [
            (
                fakes.NIFTY_ID,
                'day',
                450,
                True,
            ),
        ]

    def test_indicators_start_with_the_chart(self, tmp_path: Path) -> None:
        """Checks that warm-up history is read, then trimmed from candles and lines alike.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        document = fakes.PricesMaker().document(100)
        document['to'] = '2025-04-10'
        parts.catalogue_client.prices_by_id[fakes.NIFTY_ID] = document
        parts.log_in()
        body = parts.client.get(
            f'/api/instruments/{fakes.NIFTY_ID}/chart?days=30&indicator=sma:20'
        ).json()
        assert len(body['candles']) == 31
        points = body['indicators'][0]['outputs'][0]['points']
        assert len(points) == 31
        assert points[0][0] == body['candles'][0][0]
        assert parts.catalogue_client.price_requests[0][2] == 30 + 42

    def test_no_warm_up_without_indicators(self, tmp_path: Path) -> None:
        """Checks that a chart without indicators reads exactly its own range.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        parts.catalogue_client.prices_by_id[fakes.NIFTY_ID] = (
            fakes.PricesMaker().document(10)
        )
        parts.log_in()
        parts.client.get(f'/api/instruments/{fakes.NIFTY_ID}/chart?days=90')
        assert parts.catalogue_client.price_requests[0][2] == 90

    def test_chart_with_no_candles(self, tmp_path: Path) -> None:
        """Checks that an empty history is answered without indicators or errors.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        document = fakes.PricesMaker().document(0)
        parts.catalogue_client.prices_by_id[fakes.NIFTY_ID] = document
        parts.log_in()
        body = parts.client.get(
            f'/api/instruments/{fakes.NIFTY_ID}/chart?interval=5minute&days=30&indicator=rsi'
        ).json()
        assert body['candles'] == []
        assert body['indicators'] == []
        assert body['errors'] == []

    @pytest.mark.parametrize(
        'query',
        [
            'interval=7minute&days=30',
            'interval=5minute&days=400',
            'interval=day&days=0',
        ],
    )
    def test_chart_refuses_bad_ranges(self, tmp_path: Path, query: str) -> None:
        """Checks the interval and range checks.

        Args:
            tmp_path (Path): A temporary directory from pytest.
            query (str): The query string to send.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        parts.log_in()
        response = parts.client.get(
            f'/api/instruments/{fakes.NIFTY_ID}/chart?{query}'
        )
        assert response.status_code == 400
        assert parts.catalogue_client.price_requests == []


class TestDerivativeRoutes:
    """Tests for the /api/derivatives routes."""

    def test_underlyings(self, tmp_path: Path) -> None:
        """Checks that underlyings with derivatives are listed, index first.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        parts.log_in()
        names = []
        for entry in parts.client.get('/api/derivatives/underlyings').json():
            names.append(entry['underlying_symbol'])
        assert names[:2] == [
            'NIFTY',
            'RELIANCE',
        ]
        assert 'GOLD' in names

    def test_expiries(self, tmp_path: Path) -> None:
        """Checks the expiry description of an underlying.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        parts.log_in()
        body = parts.client.get(
            '/api/derivatives/expiries?exchange=nse&underlying=nifty'
        ).json()
        assert body['spot']['instrument_id'] == fakes.NIFTY_ID
        expiry_dates = []
        for entry in body['option_expiries']:
            expiry_dates.append(entry['expiry_date'])
        assert expiry_dates == [
            '2026-09-29',
            '2026-10-27',
        ]

    def test_chain_for_a_missing_expiry(self, tmp_path: Path) -> None:
        """Checks that an expiry without options gets 404.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        parts.log_in()
        response = parts.client.get(
            '/api/derivatives/chain?exchange=nse&underlying=NIFTY&expiry=2030-01-01'
        )
        assert response.status_code == 404

    def test_unknown_underlying(self, tmp_path: Path) -> None:
        """Checks that an underlying without derivatives gets 404.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(tmp_path / 'dist', tmp_path / 'index')
        parts.log_in()
        response = parts.client.get(
            '/api/derivatives/surface?exchange=nse&underlying=NOBODY'
        )
        assert response.status_code == 404

    def test_before_the_index_is_ready(self, tmp_path: Path) -> None:
        """Checks that derivative routes get 503 while the index is not built.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = RouteParts(
            tmp_path / 'dist',
            tmp_path / 'index',
            build_index=False,
        )
        parts.log_in()
        response = parts.client.get('/api/derivatives/underlyings')
        assert response.status_code == 503
