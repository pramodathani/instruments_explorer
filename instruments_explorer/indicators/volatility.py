"""Volatility indicators: how widely the price is swinging.

Typical usage example:

  values = BollingerBands().compute(series, {'period': 20, 'deviations': 2.0})
"""

import numpy
import talib

from instruments_explorer.indicators import base
from instruments_explorer.market import candle_series

_FAMILY = 'Volatility'


class BollingerBands(base.BaseIndicator):
    """A moving average with bands a number of standard deviations above and below."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='bbands',
            short_label='BB',
            label='Bollinger bands',
            family=_FAMILY,
            description='A moving average with bands that widen when the price swings more and narrow when it calms.',
            placement='price',
            parameters=[
                base.IndicatorParameter('period', 'Period', 20, 2, 500),
                base.IndicatorParameter(
                    'deviations',
                    'Standard deviations',
                    2.0,
                    0.5,
                    5.0,
                    whole_number=False,
                ),
            ],
            outputs=[
                (
                    'upper',
                    'Upper band',
                ),
                (
                    'middle',
                    'Middle band',
                ),
                (
                    'lower',
                    'Lower band',
                ),
            ],
        )

    def compute(
        self,
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the three bands.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): "period" and "deviations".

        Returns:
            dict[str, numpy.ndarray]: "upper", "middle" and "lower".
        """
        upper, middle, lower = talib.BBANDS(
            series.close,
            timeperiod=parameters['period'],
            nbdevup=parameters['deviations'],
            nbdevdn=parameters['deviations'],
            matype=0,
        )
        return {
            'upper': upper,
            'middle': middle,
            'lower': lower,
        }


class AverageTrueRange(base.BaseIndicator):
    """The average size of a candle's full range, gaps included."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='atr',
            short_label='ATR',
            label='Average true range',
            family=_FAMILY,
            description='How far the price typically moves in one candle, counting gaps between candles, in rupees.',
            placement='panel',
            parameters=[
                base.IndicatorParameter('period', 'Period', 14, 2, 200),
            ],
            outputs=[
                (
                    'value',
                    'ATR',
                ),
            ],
        )

    def compute(
        self,
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the average true range.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): "period".

        Returns:
            dict[str, numpy.ndarray]: "value".
        """
        return {
            'value': talib.ATR(
                series.high,
                series.low,
                series.close,
                timeperiod=parameters['period'],
            ),
        }


class NormalizedAverageTrueRange(base.BaseIndicator):
    """The average true range as a percentage of the close."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='natr',
            short_label='NATR',
            label='Normalized average true range',
            family=_FAMILY,
            description='The average true range as a percentage of the price, so instruments of any price compare.',
            placement='panel',
            parameters=[
                base.IndicatorParameter('period', 'Period', 14, 2, 200),
            ],
            outputs=[
                (
                    'value',
                    'NATR %',
                ),
            ],
        )

    def compute(
        self,
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the normalized average true range.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): "period".

        Returns:
            dict[str, numpy.ndarray]: "value", in percent.
        """
        return {
            'value': talib.NATR(
                series.high,
                series.low,
                series.close,
                timeperiod=parameters['period'],
            ),
        }
