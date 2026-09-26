"""Momentum indicators: how fast the price is moving and whether it has run too far.

Typical usage example:

  values = RelativeStrengthIndex().compute(series, {'period': 14})
"""

import numpy
import talib

from instruments_explorer.indicators import base
from instruments_explorer.market import candle_series

_FAMILY = 'Momentum'


class RelativeStrengthIndex(base.BaseIndicator):
    """The balance of recent gains against losses, from 0 to 100."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='rsi',
            short_label='RSI',
            label='Relative strength index',
            family=_FAMILY,
            description='Recent gains against recent losses on a 0 to 100 scale; above 70 is often read as overbought and below 30 as oversold.',
            placement='panel',
            parameters=[
                base.IndicatorParameter('period', 'Period', 14, 2, 200),
            ],
            outputs=[
                (
                    'value',
                    'RSI',
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
        """Computes the index.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): "period".

        Returns:
            dict[str, numpy.ndarray]: "value".
        """
        return {
            'value': talib.RSI(series.close, timeperiod=parameters['period']),
        }


class MovingAverageConvergenceDivergence(base.BaseIndicator):
    """The gap between a fast and a slow average, with a signal line."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='macd',
            short_label='MACD',
            label='MACD',
            family=_FAMILY,
            description='The gap between a fast and a slow exponential average; crossing its signal line is read as momentum turning.',
            placement='panel',
            parameters=[
                base.IndicatorParameter('fast', 'Fast period', 12, 2, 200),
                base.IndicatorParameter('slow', 'Slow period', 26, 3, 400),
                base.IndicatorParameter('signal', 'Signal period', 9, 2, 200),
            ],
            outputs=[
                (
                    'macd',
                    'MACD',
                ),
                (
                    'signal',
                    'Signal',
                ),
                (
                    'histogram',
                    'Histogram',
                ),
            ],
            reference_lines=[
                0,
            ],
        )

    def compute(
        self,
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the line, its signal and their difference.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): "fast", "slow" and "signal".

        Returns:
            dict[str, numpy.ndarray]: "macd", "signal" and "histogram".
        """
        macd, signal, histogram = talib.MACD(
            series.close,
            fastperiod=parameters['fast'],
            slowperiod=parameters['slow'],
            signalperiod=parameters['signal'],
        )
        return {
            'macd': macd,
            'signal': signal,
            'histogram': histogram,
        }


class Stochastic(base.BaseIndicator):
    """Where the close sits within the recent high-low range."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='stoch',
            short_label='Stoch',
            label='Stochastic oscillator',
            family=_FAMILY,
            description='Where the close sits in the recent high-to-low range, from 0 to 100, with a smoothed signal line.',
            placement='panel',
            parameters=[
                base.IndicatorParameter('fast_k', 'Look-back', 14, 2, 200),
                base.IndicatorParameter('slow_k', '%K smoothing', 3, 1, 50),
                base.IndicatorParameter('slow_d', '%D smoothing', 3, 1, 50),
            ],
            outputs=[
                (
                    'k',
                    '%K',
                ),
                (
                    'd',
                    '%D',
                ),
            ],
            reference_lines=[
                20,
                80,
            ],
        )

    def compute(
        self,
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes %K and %D.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): "fast_k", "slow_k" and "slow_d".

        Returns:
            dict[str, numpy.ndarray]: "k" and "d".
        """
        k_line, d_line = talib.STOCH(
            series.high,
            series.low,
            series.close,
            fastk_period=parameters['fast_k'],
            slowk_period=parameters['slow_k'],
            slowk_matype=0,
            slowd_period=parameters['slow_d'],
            slowd_matype=0,
        )
        return {
            'k': k_line,
            'd': d_line,
        }


class CommodityChannelIndex(base.BaseIndicator):
    """How far the typical price has strayed from its average."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='cci',
            short_label='CCI',
            label='Commodity channel index',
            family=_FAMILY,
            description='How far the typical price has strayed from its average, in units of its usual deviation; beyond ±100 is unusual.',
            placement='panel',
            parameters=[
                base.IndicatorParameter('period', 'Period', 20, 2, 200),
            ],
            outputs=[
                (
                    'value',
                    'CCI',
                ),
            ],
            reference_lines=[
                -100,
                100,
            ],
        )

    def compute(
        self,
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the index.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): "period".

        Returns:
            dict[str, numpy.ndarray]: "value".
        """
        return {
            'value': talib.CCI(
                series.high,
                series.low,
                series.close,
                timeperiod=parameters['period'],
            ),
        }


class WilliamsPercentRange(base.BaseIndicator):
    """Where the close sits below the recent high, from 0 to −100."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='willr',
            short_label='%R',
            label='Williams %R',
            family=_FAMILY,
            description='How far the close is below the recent high, from 0 to −100; above −20 is often read as overbought.',
            placement='panel',
            parameters=[
                base.IndicatorParameter('period', 'Period', 14, 2, 200),
            ],
            outputs=[
                (
                    'value',
                    '%R',
                ),
            ],
            reference_lines=[
                -80,
                -20,
            ],
        )

    def compute(
        self,
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes %R.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): "period".

        Returns:
            dict[str, numpy.ndarray]: "value".
        """
        return {
            'value': talib.WILLR(
                series.high,
                series.low,
                series.close,
                timeperiod=parameters['period'],
            ),
        }


class RateOfChange(base.BaseIndicator):
    """The percentage change over a number of candles."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='roc',
            short_label='ROC',
            label='Rate of change',
            family=_FAMILY,
            description='The percentage change in the close over the last so many candles.',
            placement='panel',
            parameters=[
                base.IndicatorParameter('period', 'Period', 12, 1, 400),
            ],
            outputs=[
                (
                    'value',
                    'ROC %',
                ),
            ],
            reference_lines=[
                0,
            ],
        )

    def compute(
        self,
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the rate of change.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): "period".

        Returns:
            dict[str, numpy.ndarray]: "value", in percent.
        """
        return {
            'value': talib.ROC(series.close, timeperiod=parameters['period']),
        }


class MoneyFlowIndex(base.BaseIndicator):
    """A relative strength index that also weighs volume."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='mfi',
            short_label='MFI',
            label='Money flow index',
            family=_FAMILY,
            description='Like RSI but weighted by volume, from 0 to 100; above 80 is often read as overbought.',
            placement='panel',
            parameters=[
                base.IndicatorParameter('period', 'Period', 14, 2, 200),
            ],
            outputs=[
                (
                    'value',
                    'MFI',
                ),
            ],
            reference_lines=[
                20,
                80,
            ],
            needs_volume=True,
        )

    def compute(
        self,
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the index, treating a missing volume as zero.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): "period".

        Returns:
            dict[str, numpy.ndarray]: "value".
        """
        return {
            'value': talib.MFI(
                series.high,
                series.low,
                series.close,
                numpy.nan_to_num(series.volume),
                timeperiod=parameters['period'],
            ),
        }
