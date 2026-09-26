"""Volume indicators: whether money is flowing into or out of the instrument.

Typical usage example:

  values = OnBalanceVolume().compute(analysis, {})
"""

import numpy
from tradingmachine.assets.analysis import candle_frame_analysis

from instruments_explorer.indicators import base

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
        analysis: candle_frame_analysis.CandleFrameAnalysis,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the running volume total with tradingmachine, counting missing volume as zero.

        Args:
            analysis (candle_frame_analysis.CandleFrameAnalysis): The candles, ready for tradingmachine's analysis methods.
            parameters (dict[str, float]): None are used.

        Returns:
            dict[str, numpy.ndarray]: "value".
        """
        del parameters
        frame = analysis.on_balance_volume()
        return {
            'value': self.column(frame, 'obv'),
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
        analysis: candle_frame_analysis.CandleFrameAnalysis,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the accumulation/distribution line with tradingmachine, counting missing volume as zero.

        Args:
            analysis (candle_frame_analysis.CandleFrameAnalysis): The candles, ready for tradingmachine's analysis methods.
            parameters (dict[str, float]): None are used.

        Returns:
            dict[str, numpy.ndarray]: "value".
        """
        del parameters
        frame = analysis.chaikin_accumulation_distribution_line()
        return {
            'value': self.column(frame, 'chaikin_ad'),
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
        analysis: candle_frame_analysis.CandleFrameAnalysis,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the oscillator with tradingmachine, counting missing volume as zero.

        Args:
            analysis (candle_frame_analysis.CandleFrameAnalysis): The candles, ready for tradingmachine's analysis methods.
            parameters (dict[str, float]): "fast" and "slow".

        Returns:
            dict[str, numpy.ndarray]: "value".
        """
        fast = int(parameters['fast'])
        slow = int(parameters['slow'])
        frame = analysis.chaikin_accumulation_distribution_oscillator(
            fast_period=fast,
            slow_period=slow,
        )
        return {
            'value': self.column(frame, f'chaikin_adosc{fast}_{slow}'),
        }
