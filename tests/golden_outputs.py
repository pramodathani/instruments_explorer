"""Computes the indicator, screener and chart outputs that the golden files record.

The same computation writes the golden files once and checks against them on every test run, so any change to a number the browser or the screener sees is caught.

Typical usage example:

  outputs = GoldenOutputs().compute('reliance_day')
"""

import gzip
import json
import pathlib
from typing import Any

import fastapi

from instruments_explorer.indicators import indicator_calculator
from instruments_explorer.indicators import indicator_catalogue
from instruments_explorer.market import candle_series
from instruments_explorer.routes import chart_routes
from instruments_explorer.screener import stock_metrics

FIXTURES_DIRECTORY = pathlib.Path(__file__).parent / 'fixtures'
PRICES_DIRECTORY = FIXTURES_DIRECTORY / 'prices'
GOLDEN_DIRECTORY = FIXTURES_DIRECTORY / 'golden'
FIXTURE_NAMES = [
    'reliance_day',
    'reliance_day_unadjusted',
    'nifty_day',
    'gold_future_day',
    'synthetic_missing_volume',
    'synthetic_gaps',
    'synthetic_short',
    'synthetic_flat',
    'synthetic_5minute',
]
NON_DEFAULT_REQUESTS = [
    'sma:50',
    'ema:9',
    'wma:15',
    'dema:15',
    'tema:30',
    'bbands:20:2.5',
    'atr:10',
    'natr:7',
    'sar:0.01:0.1',
    'adx:10',
    'aroon:25',
    'rsi:7',
    'macd:5:35:5',
    'stoch:14:3:5',
    'cci:14',
    'willr:21',
    'roc:5',
    'mfi:10',
    'adosc:5:20',
]


class _OpenGuard:
    """A session guard that lets every request through, because the golden outputs call the route's methods directly."""

    def require_session(self, request: fastapi.Request) -> None:
        """Accepts every request.

        Args:
            request (fastapi.Request): The request.
        """
        del request


class GoldenOutputs:
    """Computes the recorded outputs for one prices fixture."""

    def __init__(self):
        """Creates the catalogue, calculator, screener metrics and chart routes the outputs come from."""
        self._catalogue = indicator_catalogue.IndicatorCatalogue()
        self._calculator = indicator_calculator.IndicatorCalculator(
            self._catalogue
        )
        self._metrics = stock_metrics.StockMetrics()
        self._chart = chart_routes.ChartRoutes(
            None,
            self._catalogue,
            _OpenGuard(),
        )

    def load_prices(self, name: str) -> dict[str, Any]:
        """Reads one prices fixture.

        Args:
            name (str): The fixture's name, without the .json suffix.

        Returns:
            dict[str, Any]: UBI's prices document.
        """
        path = PRICES_DIRECTORY / f'{name}.json'
        return json.loads(path.read_text())

    def requests(self) -> list[str]:
        """Lists every indicator request the golden outputs cover.

        Returns:
            list[str]: Every indicator key at its defaults, followed by NON_DEFAULT_REQUESTS.
        """
        requests = []
        for description in self._catalogue.describe():
            requests.append(description['key'])
        requests.extend(NON_DEFAULT_REQUESTS)
        return requests

    def compute(self, name: str) -> dict[str, Any]:
        """Computes every recorded output for one fixture.

        Args:
            name (str): The fixture's name.

        Returns:
            dict[str, Any]: "indicators" with one calculator answer per request, "metrics" with the screener's figures, and "charts" with the chart route's answers.
        """
        document = self.load_prices(name)
        series = candle_series.CandleSeries.from_prices_document(document)
        indicators = {}
        for request in self.requests():
            results, errors = self._calculator.compute(
                series,
                [
                    request,
                ],
            )
            indicators[request] = {
                'results': results,
                'errors': errors,
            }
        return {
            'indicators': indicators,
            'metrics': self._metrics.compute(series),
            'charts': self._charts(document),
        }

    def canonical_text(self, outputs: dict[str, Any]) -> str:
        """Writes outputs as JSON text in a fixed form, so two runs can be compared as text.

        Args:
            outputs (dict[str, Any]): The outputs from compute.

        Returns:
            str: Compact JSON with sorted keys, where floats round-trip exactly and NaN is written as NaN.
        """
        return json.dumps(
            outputs,
            sort_keys=True,
            separators=(
                ',',
                ':',
            ),
        )

    def read_golden(self, name: str) -> str:
        """Reads one fixture's golden file.

        Args:
            name (str): The fixture's name.

        Returns:
            str: The recorded canonical text.
        """
        return gzip.decompress(self.golden_path(name).read_bytes()).decode()

    def write_golden(self, name: str) -> None:
        """Records one fixture's outputs as its golden file.

        Args:
            name (str): The fixture's name.
        """
        text = self.canonical_text(self.compute(name))
        compressed = gzip.compress(text.encode(), mtime=0)
        self.golden_path(name).write_bytes(compressed)

    def golden_path(self, name: str) -> pathlib.Path:
        """Names the golden file of one fixture.

        Args:
            name (str): The fixture's name.

        Returns:
            pathlib.Path: The golden file's path, a gzip-compressed JSON file.
        """
        return GOLDEN_DIRECTORY / f'{name}.json.gz'

    def _charts(self, document: dict[str, Any]) -> dict[str, Any]:
        """Builds the chart route's answers for the fixture, in groups small enough for one chart.

        Args:
            document (dict[str, Any]): UBI's prices document.

        Returns:
            dict[str, Any]: One chart answer per group of requests, keyed by the group's position.
        """
        interval = document.get('interval') or 'day'
        days = 365 if interval == 'day' else 10
        requests = self.requests()
        charts = {}
        group_size = indicator_calculator.MAXIMUM_INDICATORS
        for start in range(0, len(requests), group_size):
            group = requests[start : start + group_size]
            charts[str(start // group_size)] = self._chart._build_answer(
                'golden',
                interval,
                days,
                document,
                group,
            )
        return charts
