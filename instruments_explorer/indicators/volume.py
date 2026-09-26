"""Volume indicators: whether money is flowing into or out of the instrument.

Typical usage example:

  values = OnBalanceVolume().compute(series, {})
"""

import numpy
import talib

from instruments_explorer.indicators import base
from instruments_explorer.market import candle_series

_FAMILY = 'Volume'


class OnBalanceVolume(base.BaseIndicator):
    """A running total that adds volume on up candles and subtracts it on down candles."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='obv',
            short_label='OBV',
            label='On-balance volume',
            family=_FAMILY,
            description='A running total of volume, added on days the close rises and subtracted on days it falls.',
            placement='panel',
            parameters=[],
            outputs=[
                (
                    'value',
                    'OBV',
                ),
            ],
            needs_volume=True,
        )

    def compute(
        self,
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the running total, treating a missing volume as zero.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): None are used.

        Returns:
            dict[str, numpy.ndarray]: "value".
        """
        del parameters
        return {
            'value': talib.OBV(series.close, numpy.nan_to_num(series.volume)),
        }


class AccumulationDistribution(base.BaseIndicator):
    """A running total of volume weighted by where each close sits in its candle."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='ad',
            short_label='A/D',
            label='Accumulation/distribution line',
            family=_FAMILY,
            description='A running total of volume, weighted by whether each candle closed near its high or its low.',
            placement='panel',
            parameters=[],
            outputs=[
                (
                    'value',
                    'A/D',
                ),
            ],
            needs_volume=True,
        )

    def compute(
        self,
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the line, treating a missing volume as zero.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): None are used.

        Returns:
            dict[str, numpy.ndarray]: "value".
        """
        del parameters
        return {
            'value': talib.AD(
                series.high,
                series.low,
                series.close,
                numpy.nan_to_num(series.volume),
            ),
        }


class ChaikinOscillator(base.BaseIndicator):
    """The momentum of the accumulation/distribution line."""

    def __init__(self):
        """Describes the indicator."""
        super().__init__(
            key='adosc',
            short_label='Chaikin',
            label='Chaikin oscillator',
            family=_FAMILY,
            description='The gap between a fast and a slow average of the accumulation/distribution line.',
            placement='panel',
            parameters=[
                base.IndicatorParameter('fast', 'Fast period', 3, 2, 100),
                base.IndicatorParameter('slow', 'Slow period', 10, 3, 200),
            ],
            outputs=[
                (
                    'value',
                    'Chaikin',
                ),
            ],
            reference_lines=[
                0,
            ],
            needs_volume=True,
        )

    def compute(
        self,
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the oscillator, treating a missing volume as zero.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): "fast" and "slow".

        Returns:
            dict[str, numpy.ndarray]: "value".
        """
        return {
            'value': talib.ADOSC(
                series.high,
                series.low,
                series.close,
                numpy.nan_to_num(series.volume),
                fastperiod=parameters['fast'],
                slowperiod=parameters['slow'],
            ),
        }
