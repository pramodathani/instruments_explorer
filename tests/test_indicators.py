"""Tests for candle series, indicators, the catalogue and the calculator."""

import numpy
import pytest

from instruments_explorer.indicators import base
from instruments_explorer.indicators import indicator_calculator
from instruments_explorer.indicators import indicator_catalogue
from instruments_explorer.indicators import moving_averages
from instruments_explorer.market import candle_series
from tests import fakes


class TestCandleSeries:
    """Tests for CandleSeries."""

    def test_from_prices_document(self) -> None:
        """Checks times in epoch milliseconds and the column arrays."""
        document = fakes.PricesMaker().document(3)
        series = candle_series.CandleSeries.from_prices_document(document)
        assert len(series) == 3
        assert series.times[0] == 1735689600000
        assert series.times[1] - series.times[0] == 86_400_000
        assert series.close[0] == pytest.approx(1000.0)
        assert numpy.isnan(series.oi[0])

    def test_candles_without_a_close_are_skipped(self) -> None:
        """Checks that a row missing its close is left out."""
        document = fakes.PricesMaker().document(3)
        document['candles'][1][4] = None
        series = candle_series.CandleSeries.from_prices_document(document)
        assert len(series) == 2

    def test_rows_write_missing_values_as_none(self) -> None:
        """Checks the compact rows."""
        document = fakes.PricesMaker().document(1)
        row = candle_series.CandleSeries.from_prices_document(document).rows()[
            0
        ]
        assert row[0] == 1735689600000
        assert row[6] is None

    def test_has_volume(self) -> None:
        """Checks that an all-zero volume counts as none."""
        maker = fakes.PricesMaker()
        with_volume = candle_series.CandleSeries.from_prices_document(
            maker.document(5)
        )
        without_volume = candle_series.CandleSeries.from_prices_document(
            maker.document(5, with_volume=False)
        )
        assert with_volume.has_volume()
        assert not without_volume.has_volume()


class TestIndicatorParameters:
    """Tests for IndicatorParameter and BaseIndicator.resolve."""

    def test_parse_checks_range_and_whole_numbers(self) -> None:
        """Checks the three kinds of invalid value."""
        parameter = base.IndicatorParameter('period', 'Period', 14, 2, 200)
        assert parameter.parse('20') == 20
        with pytest.raises(ValueError, match='whole number'):
            parameter.parse('2.5')
        with pytest.raises(ValueError, match='between'):
            parameter.parse('1')
        with pytest.raises(ValueError, match='a number'):
            parameter.parse('ten')

    def test_resolve_fills_defaults(self) -> None:
        """Checks that parameters left out take their defaults."""
        catalogue = indicator_catalogue.IndicatorCatalogue()
        macd = catalogue.find('macd')
        assert macd.resolve(['8']) == {
            'fast': 8,
            'slow': 26,
            'signal': 9,
        }

    def test_resolve_refuses_extra_values(self) -> None:
        """Checks that too many values are refused."""
        with pytest.raises(ValueError, match='at most'):
            moving_averages.SimpleMovingAverage().resolve(
                [
                    '20',
                    '30',
                ]
            )

    def test_title(self) -> None:
        """Checks the legend names."""
        catalogue = indicator_catalogue.IndicatorCatalogue()
        bands = catalogue.find('bbands')
        assert bands.title(bands.resolve([])) == 'BB 20, 2'
        assert catalogue.find('obv').title({}) == 'OBV'


class TestEveryIndicator:
    """Runs every indicator in the catalogue over made-up candles."""

    def test_every_indicator_computes_aligned_arrays(self) -> None:
        """Checks that each output has one value per candle and ends with a number."""
        series = candle_series.CandleSeries.from_prices_document(
            fakes.PricesMaker().document(200)
        )
        catalogue = indicator_catalogue.IndicatorCatalogue()
        for description in catalogue.describe():
            indicator = catalogue.find(description['key'])
            values = indicator.compute(series, indicator.resolve([]))
            output_keys = []
            for output_key, _ in indicator.outputs:
                output_keys.append(output_key)
            assert sorted(values) == sorted(output_keys), indicator.key
            for array in values.values():
                assert len(array) == len(series), indicator.key
                assert not numpy.isnan(array[-1]), indicator.key

    def test_keys_are_unique(self) -> None:
        """Checks that no two indicators share a key."""
        keys = []
        for description in indicator_catalogue.IndicatorCatalogue().describe():
            keys.append(description['key'])
        assert len(keys) == len(set(keys))


class TestIndicatorCalculator:
    """Tests for IndicatorCalculator."""

    def _calculator(self) -> indicator_calculator.IndicatorCalculator:
        """Builds a calculator over the real catalogue.

        Returns:
            indicator_calculator.IndicatorCalculator: The calculator.
        """
        return indicator_calculator.IndicatorCalculator(
            indicator_catalogue.IndicatorCatalogue()
        )

    def test_points_start_after_the_warm_up(self) -> None:
        """Checks that NaN values before the first full period are left out."""
        series = candle_series.CandleSeries.from_prices_document(
            fakes.PricesMaker().document(50)
        )
        results, errors = self._calculator().compute(
            series,
            [
                'SMA:20',
            ],
        )
        assert errors == []
        points = results[0]['outputs'][0]['points']
        assert len(points) == 31
        assert points[0][0] == series.times[19]
        assert results[0]['id'] == 'sma:20'
        assert results[0]['placement'] == 'price'

    def test_errors_are_collected(self) -> None:
        """Checks that bad requests become messages and good ones still compute."""
        series = candle_series.CandleSeries.from_prices_document(
            fakes.PricesMaker().document(50, with_volume=False)
        )
        results, errors = self._calculator().compute(
            series,
            [
                'nonsense',
                'rsi:1',
                'obv',
                'rsi:14',
            ],
        )
        assert len(results) == 1
        assert results[0]['reference_lines'] == [
            30,
            70,
        ]
        assert len(errors) == 3
        assert "Unknown indicator: 'nonsense'" in errors
        assert (
            'On-balance volume needs volume, and this instrument has none.'
            in errors
        )

    def test_patterns_become_markers(self) -> None:
        """Checks the shape of pattern markers."""
        series = candle_series.CandleSeries.from_prices_document(
            fakes.PricesMaker().document(120)
        )
        results, _ = self._calculator().compute(
            series,
            [
                'patterns',
            ],
        )
        result = results[0]
        assert result['outputs'] == []
        times = []
        for marker in result['markers']:
            assert set(marker) == {
                'time',
                'pattern',
                'label',
                'bullish',
            }
            times.append(marker['time'])
        assert times == sorted(times)

    def test_too_many_indicators(self) -> None:
        """Checks the limit on indicators per chart."""
        series = candle_series.CandleSeries.from_prices_document(
            fakes.PricesMaker().document(60)
        )
        requests = []
        for period in range(2, 2 + indicator_calculator.MAXIMUM_INDICATORS + 3):
            requests.append(f'sma:{period}')
        results, errors = self._calculator().compute(series, requests)
        assert len(results) == indicator_calculator.MAXIMUM_INDICATORS
        assert len(errors) == 1
