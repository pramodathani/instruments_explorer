"""Trend indicators: which way the price is heading and how strongly.

Typical usage example:

  values = AverageDirectionalIndex().compute(series, {'period': 14})
"""

import numpy
import talib

from instruments_explorer.indicators import base
from instruments_explorer.market import candle_series

_FAMILY = 'Trend'


class ParabolicSar(base.BaseIndicator):
    """Stop-and-reverse dots that trail the price and flip sides when the trend turns."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='sar',
            short_label='SAR',
            label='Parabolic SAR',
            family=_FAMILY,
            description='Dots that trail below a rising price and above a falling one, flipping side when the trend turns.',
            placement='price',
            parameters=[
                base.IndicatorParameter(
                    'acceleration',
                    'Acceleration',
                    0.02,
                    0.001,
                    0.5,
                    whole_number=False,
                ),
                base.IndicatorParameter(
                    'maximum',
                    'Maximum acceleration',
                    0.2,
                    0.01,
                    1.0,
                    whole_number=False,
                ),
            ],
            outputs=[
                (
                    'value',
                    'SAR',
                ),
            ],
        )

    def compute(
        self,
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the stop-and-reverse level.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): "acceleration" and "maximum".

        Returns:
            dict[str, numpy.ndarray]: "value".
        """
        return {
            'value': talib.SAR(
                series.high,
                series.low,
                acceleration=parameters['acceleration'],
                maximum=parameters['maximum'],
            ),
        }


class AverageDirectionalIndex(base.BaseIndicator):
    """How strong the trend is, with the upward and downward pressure behind it."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='adx',
            short_label='ADX',
            label='Average directional index',
            family=_FAMILY,
            description='How strong the trend is, whichever way it runs; above 25 is usually read as a trend.',
            placement='panel',
            parameters=[
                base.IndicatorParameter('period', 'Period', 14, 2, 200),
            ],
            outputs=[
                (
                    'adx',
                    'ADX',
                ),
                (
                    'plus',
                    '+DI',
                ),
                (
                    'minus',
                    '−DI',
                ),
            ],
            reference_lines=[
                25,
            ],
        )

    def compute(
        self,
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the index and its two directional lines.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): "period".

        Returns:
            dict[str, numpy.ndarray]: "adx", "plus" and "minus".
        """
        period = parameters['period']
        return {
            'adx': talib.ADX(
                series.high,
                series.low,
                series.close,
                timeperiod=period,
            ),
            'plus': talib.PLUS_DI(
                series.high,
                series.low,
                series.close,
                timeperiod=period,
            ),
            'minus': talib.MINUS_DI(
                series.high,
                series.low,
                series.close,
                timeperiod=period,
            ),
        }


class Aroon(base.BaseIndicator):
    """How recently the highest high and the lowest low happened."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='aroon',
            short_label='Aroon',
            label='Aroon',
            family=_FAMILY,
            description='How recently the period’s highest high and lowest low happened; a fresh high keeps Aroon up near 100.',
            placement='panel',
            parameters=[
                base.IndicatorParameter('period', 'Period', 25, 2, 200),
            ],
            outputs=[
                (
                    'up',
                    'Aroon up',
                ),
                (
                    'down',
                    'Aroon down',
                ),
            ],
            reference_lines=[
                30,
                70,
            ],
        )

    def compute(
        self,
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the up and down lines.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): "period".

        Returns:
            dict[str, numpy.ndarray]: "up" and "down".
        """
        down, up = talib.AROON(
            series.high,
            series.low,
            timeperiod=parameters['period'],
        )
        return {
            'up': up,
            'down': down,
        }
