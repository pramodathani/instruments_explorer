"""Moving averages, drawn over the candles.

Typical usage example:

  values = SimpleMovingAverage().compute(series, {'period': 50})
"""

import numpy
import talib

from instruments_explorer.indicators import base
from instruments_explorer.market import candle_series

_FAMILY = 'Moving averages'


class SimpleMovingAverage(base.BaseIndicator):
    """The plain average of the last closes."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='sma',
            short_label='SMA',
            label='Simple moving average',
            family=_FAMILY,
            description='The average close of the last so many candles, which smooths out day-to-day noise.',
            placement='price',
            parameters=[
                base.IndicatorParameter('period', 'Period', 20, 2, 500),
            ],
            outputs=[
                (
                    'value',
                    'SMA',
                ),
            ],
        )

    def compute(
        self,
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the average.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): "period".

        Returns:
            dict[str, numpy.ndarray]: "value".
        """
        return {
            'value': talib.SMA(series.close, timeperiod=parameters['period']),
        }


class ExponentialMovingAverage(base.BaseIndicator):
    """An average that weighs recent closes more."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='ema',
            short_label='EMA',
            label='Exponential moving average',
            family=_FAMILY,
            description='An average that gives recent closes more weight, so it turns sooner than the simple average.',
            placement='price',
            parameters=[
                base.IndicatorParameter('period', 'Period', 20, 2, 500),
            ],
            outputs=[
                (
                    'value',
                    'EMA',
                ),
            ],
        )

    def compute(
        self,
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the average.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): "period".

        Returns:
            dict[str, numpy.ndarray]: "value".
        """
        return {
            'value': talib.EMA(series.close, timeperiod=parameters['period']),
        }


class WeightedMovingAverage(base.BaseIndicator):
    """An average whose weights fall in a straight line with age."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='wma',
            short_label='WMA',
            label='Weighted moving average',
            family=_FAMILY,
            description='An average whose weights fall in a straight line from the newest close to the oldest.',
            placement='price',
            parameters=[
                base.IndicatorParameter('period', 'Period', 20, 2, 500),
            ],
            outputs=[
                (
                    'value',
                    'WMA',
                ),
            ],
        )

    def compute(
        self,
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the average.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): "period".

        Returns:
            dict[str, numpy.ndarray]: "value".
        """
        return {
            'value': talib.WMA(series.close, timeperiod=parameters['period']),
        }


class DoubleExponentialMovingAverage(base.BaseIndicator):
    """An exponential average with less lag."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='dema',
            short_label='DEMA',
            label='Double exponential moving average',
            family=_FAMILY,
            description='An exponential average corrected for its own lag, so it follows the price more closely.',
            placement='price',
            parameters=[
                base.IndicatorParameter('period', 'Period', 20, 2, 500),
            ],
            outputs=[
                (
                    'value',
                    'DEMA',
                ),
            ],
        )

    def compute(
        self,
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the average.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): "period".

        Returns:
            dict[str, numpy.ndarray]: "value".
        """
        return {
            'value': talib.DEMA(series.close, timeperiod=parameters['period']),
        }


class TripleExponentialMovingAverage(base.BaseIndicator):
    """An exponential average with even less lag."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='tema',
            short_label='TEMA',
            label='Triple exponential moving average',
            family=_FAMILY,
            description='An exponential average corrected for lag twice over, the quickest of the averages here.',
            placement='price',
            parameters=[
                base.IndicatorParameter('period', 'Period', 20, 2, 500),
            ],
            outputs=[
                (
                    'value',
                    'TEMA',
                ),
            ],
        )

    def compute(
        self,
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the average.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): "period".

        Returns:
            dict[str, numpy.ndarray]: "value".
        """
        return {
            'value': talib.TEMA(series.close, timeperiod=parameters['period']),
        }
