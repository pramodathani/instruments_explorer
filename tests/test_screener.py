"""Tests for the screener: stock figures, conditions, the service and the scheduler."""

import asyncio
import datetime
from pathlib import Path

import numpy
import pytest

from instruments_explorer.instruments import instrument_index_builder
from instruments_explorer.instruments import instrument_index_maintainer
from instruments_explorer.market import candle_series
from instruments_explorer.screener import screener_scheduler
from instruments_explorer.screener import screener_service
from instruments_explorer.screener import screener_universe
from instruments_explorer.screener import snapshot_job
from instruments_explorer.screener import stock_metrics
from instruments_explorer.screener.conditions import condition_catalogue
from instruments_explorer.storage import company_repository
from instruments_explorer.storage import screener_repository
from tests import fakes

_INDIA = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


class TestStockMetrics:
    """Tests for StockMetrics."""

    def test_too_short(self) -> None:
        """Checks that a short history gives no figures."""
        series = candle_series.CandleSeries.from_prices_document(
            fakes.PricesMaker().document(10)
        )
        assert stock_metrics.StockMetrics().compute(series) is None

    def test_figures(self) -> None:
        """Checks the returns, range, averages and volume figures of a known series."""
        series = candle_series.CandleSeries.from_prices_document(
            fakes.PricesMaker().document(300)
        )
        figures = stock_metrics.StockMetrics().compute(series)
        close = series.close
        assert figures['close'] == pytest.approx(close[-1], abs=1e-4)
        assert figures['change_1d'] == pytest.approx(
            (close[-1] / close[-2] - 1) * 100,
            abs=1e-3,
        )
        assert figures['change_252d'] is not None
        assert figures['from_high'] <= 0
        assert figures['from_low'] >= 0
        assert 0 <= figures['rsi_14'] <= 100
        assert figures['sma_200'] is not None
        assert figures['above_sma_20'] in (True, False)
        assert figures['volume_ratio'] == pytest.approx(3990 / 3885, abs=1e-3)
        assert figures['last_candle_date'] == '2025-10-27'

    def test_cross_detection(self) -> None:
        """Checks that a crossing is found, and how many candles ago."""
        metrics = stock_metrics.StockMetrics()
        fast = numpy.array(
            [
                1.0,
                1.0,
                1.0,
                3.0,
                3.0,
            ]
        )
        slow = numpy.full(5, 2.0)
        assert metrics._days_since_cross(fast, slow, upward=True) == 1
        assert metrics._days_since_cross(fast, slow, upward=False) is None


class TestConditions:
    """Tests for the conditions."""

    def _check(self, request: str, figures: dict) -> bool:
        """Resolves a request and tests figures against it.

        Args:
            request (str): The request, such as "rsi:0:30".
            figures (dict): The figures.

        Returns:
            bool: Whether the figures match.
        """
        pieces = request.split(':')
        condition = condition_catalogue.ConditionCatalogue().find(pieces[0])
        return condition.matches(figures, condition.resolve(pieces[1:]))

    def test_each_condition(self) -> None:
        """Checks every condition with one matching and one failing case."""
        cases = [
            ('rsi:0:30', {'rsi_14': 25.0}, {'rsi_14': 45.0}),
            ('return:21:10', {'change_21d': 12.0}, {'change_21d': 3.0}),
            (
                'above_average:200',
                {'above_sma_200': True},
                {'above_sma_200': None},
            ),
            (
                'below_average:50',
                {'above_sma_50': False},
                {'above_sma_50': True},
            ),
            (
                'golden_cross:10',
                {'golden_cross_days': 3},
                {'golden_cross_days': None},
            ),
            ('death_cross:5', {'death_cross_days': 5}, {'death_cross_days': 9}),
            ('macd_turn:5', {'macd_cross_days': 0}, {}),
            ('near_high:5', {'from_high': -2.0}, {'from_high': -8.0}),
            ('near_low:5', {'from_low': 4.0}, {'from_low': 12.0}),
            ('volume_spike:2', {'volume_ratio': 2.5}, {'volume_ratio': 1.2}),
            ('strong_trend:25', {'adx_14': 31.0}, {'adx_14': 12.0}),
        ]
        catalogue = condition_catalogue.ConditionCatalogue()
        assert len(cases) == len(catalogue.describe())
        for request, matching, failing in cases:
            assert self._check(request, matching), request
            assert not self._check(request, failing), request

    def test_invalid_periods(self) -> None:
        """Checks that periods the figures do not hold are refused."""
        catalogue = condition_catalogue.ConditionCatalogue()
        with pytest.raises(ValueError, match='trading days'):
            catalogue.find('return').resolve(['7'])
        with pytest.raises(ValueError, match='average must be'):
            catalogue.find('above_average').resolve(['100'])


class UniverseMaker:
    """Builds a universe over the made-up catalogue with RELIANCE in the Nifty Total Market."""

    def build(
        self,
        directory: Path,
        database: fakes.FakeDatabase,
    ) -> tuple[screener_universe.ScreenerUniverse, fakes.FakeCatalogueClient]:
        """Builds the index, the companies and the universe.

        Args:
            directory (Path): Where to build the index.
            database (fakes.FakeDatabase): The fake database.

        Returns:
            tuple[screener_universe.ScreenerUniverse, fakes.FakeCatalogueClient]: A tuple (the universe, the stand-in UBI client).
        """
        client = fakes.FakeCatalogueClient(fakes.CatalogueMaker().catalogue())
        time_source = fakes.FixedClock(fakes.TODAY_EPOCH)
        maintainer = instrument_index_maintainer.InstrumentIndexMaintainer(
            client,
            instrument_index_builder.InstrumentIndexBuilder(
                client,
                directory,
                time_source,
            ),
            time_source,
        )
        asyncio.run(maintainer.refresh())
        companies = company_repository.CompanyRepository(database)
        asyncio.run(
            companies.set_index_industries(
                [
                    {
                        'company_key': 'INE002A01018',
                        'name': 'Reliance Industries Ltd.',
                        'industry': 'Oil Gas & Consumable Fuels',
                        'symbol': 'RELIANCE',
                        'isin': 'INE002A01018',
                    },
                    {
                        'company_key': 'NOPE',
                        'name': 'Not In The Index',
                        'industry': 'Healthcare',
                        'symbol': 'NOPE',
                        'isin': 'NOPE',
                    },
                ],
                1.0,
            )
        )
        return screener_universe.ScreenerUniverse(maintainer, companies), client


class TestUniverseAndJob:
    """Tests for ScreenerUniverse, ScreenerSnapshotJob and ScreenerService."""

    def test_members_need_an_instrument(self, tmp_path: Path) -> None:
        """Checks that a company the index does not know is left out.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        universe, _ = UniverseMaker().build(tmp_path, fakes.FakeDatabase())
        members = asyncio.run(universe.members('total_market'))
        assert members == [
            {
                'instrument_id': fakes.RELIANCE_NSE_ID,
                'symbol': 'RELIANCE',
                'name': 'Reliance Industries Ltd.',
                'sector': 'Oil Gas & Consumable Fuels',
            },
        ]
        with pytest.raises(ValueError, match='Unknown screener universe'):
            asyncio.run(universe.members('everything'))

    def test_job_and_screen(self, tmp_path: Path) -> None:
        """Checks a run's counts and a screen's rows, sorting and sector groups.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        database = fakes.FakeDatabase()
        universe, client = UniverseMaker().build(tmp_path, database)
        client.prices_by_id[fakes.RELIANCE_NSE_ID] = (
            fakes.PricesMaker().document(300)
        )
        repository = screener_repository.ScreenerRepository(database)
        announced = []
        job = snapshot_job.ScreenerSnapshotJob(
            universe,
            client,
            repository,
            announced.append,
            fakes.FixedClock(5.0),
        )
        service = screener_service.ScreenerService(
            universe,
            repository,
            condition_catalogue.ConditionCatalogue(),
        )

        async def run_and_screen() -> tuple[dict, dict, dict]:
            """Runs the job to the end, then two screens.

            Returns:
                tuple[dict, dict, dict]: A tuple (the run's state, a screen that matches, a screen that does not).
            """
            state = await job.start('total_market')
            while job.running():
                await asyncio.sleep(0.01)
            matching = await service.run(
                'total_market',
                [
                    'rsi:0:100',
                ],
                [],
                'change_1d',
                True,
                10,
            )
            failing = await service.run(
                'total_market',
                [
                    'rsi:0:100',
                ],
                [
                    'Healthcare',
                ],
                'symbol',
                False,
                10,
            )
            return state, matching, failing

        state, matching, failing = asyncio.run(run_and_screen())
        assert state['status'] == 'done'
        assert state['done'] == 1
        assert announced[-1]['type'] == 'screener_job'
        assert matching['matched'] == 1
        assert matching['sectors'][0]['count'] == 1
        assert matching['last_run']['status'] == 'done'
        assert failing['matched'] == 0
        assert failing['sector_names'] == [
            'Oil Gas & Consumable Fuels',
        ]

    def test_failed_stock_is_counted(self, tmp_path: Path) -> None:
        """Checks that a stock UBI has no candles for is counted as failed.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        database = fakes.FakeDatabase()
        universe, _ = UniverseMaker().build(tmp_path, database)
        job = snapshot_job.ScreenerSnapshotJob(
            universe,
            fakes.FakeCatalogueClient([]),
            screener_repository.ScreenerRepository(database),
            lambda message: None,
            fakes.FixedClock(5.0),
        )

        async def run() -> dict:
            """Runs the job to the end.

            Returns:
                dict: The run's state.
            """
            await job.start('total_market')
            while job.running():
                await asyncio.sleep(0.01)
            return job.state

        state = asyncio.run(run())
        assert state['failed'] == 1
        assert state['done'] == 0

    def test_service_refuses_bad_requests(self, tmp_path: Path) -> None:
        """Checks the sort, limit and condition checks.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        database = fakes.FakeDatabase()
        universe, _ = UniverseMaker().build(tmp_path, database)
        service = screener_service.ScreenerService(
            universe,
            screener_repository.ScreenerRepository(database),
            condition_catalogue.ConditionCatalogue(),
        )
        with pytest.raises(ValueError, match='sort'):
            asyncio.run(service.run('total_market', [], [], 'secret', True, 10))
        with pytest.raises(ValueError, match='limit'):
            asyncio.run(service.run('total_market', [], [], 'symbol', True, 0))
        with pytest.raises(ValueError, match='Unknown screening condition'):
            asyncio.run(
                service.run('total_market', ['nope'], [], 'symbol', True, 10)
            )


class TestScreenerScheduler:
    """Tests for ScreenerScheduler.due."""

    def _scheduler(
        self, hour: int, last_started: float | None
    ) -> screener_scheduler.ScreenerScheduler:
        """Builds a scheduler at an India hour with a prepared last run.

        Args:
            hour (int): The hour of day in India.
            last_started (float | None): When the last finished run started, or None for none.

        Returns:
            screener_scheduler.ScreenerScheduler: The scheduler.
        """
        now = datetime.datetime(2026, 9, 28, hour, 0, tzinfo=_INDIA).timestamp()
        database = fakes.FakeDatabase()
        repository = screener_repository.ScreenerRepository(database)
        if last_started is not None:
            asyncio.run(
                repository.save_run(
                    {
                        'run_id': 'r',
                        'universe': 'total_market',
                        'status': 'done',
                        'started_at': now - last_started,
                    }
                )
            )
        job = snapshot_job.ScreenerSnapshotJob(
            None,
            None,
            repository,
            lambda message: None,
            fakes.FixedClock(now),
        )
        return screener_scheduler.ScreenerScheduler(
            job,
            repository,
            fakes.FixedClock(now),
        )

    def test_due(self) -> None:
        """Checks the hour and staleness rules."""
        assert asyncio.run(self._scheduler(10, None).due())
        assert not asyncio.run(self._scheduler(8, None).due())
        assert not asyncio.run(self._scheduler(10, 3600).due())
        assert asyncio.run(self._scheduler(10, 21 * 3600).due())
