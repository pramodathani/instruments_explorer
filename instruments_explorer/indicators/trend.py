"""Trend indicators: which way the price is heading and how strongly.

Typical usage example:

  values = AverageDirectionalIndex().compute(analysis, {'period': 14})
"""

import numpy
from tradingmachine.assets.analysis import candle_frame_analysis

from instruments_explorer.indicators import base

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
        analysis: candle_frame_analysis.CandleFrameAnalysis,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the stop-and-reverse level with tradingmachine.

        Args:
            analysis (candle_frame_analysis.CandleFrameAnalysis): The candles, ready for tradingmachine's analysis methods.
            parameters (dict[str, float]): "acceleration" and "maximum".

        Returns:
            dict[str, numpy.ndarray]: "value".
        """
        frame = analysis.parabolic_sar(
            acceleration=parameters['acceleration'],
            maximum=parameters['maximum'],
        )
        return {
            'value': self.column(frame, 'psar'),
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
        analysis: candle_frame_analysis.CandleFrameAnalysis,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the index and its two directional lines with tradingmachine.

        Args:
            analysis (candle_frame_analysis.CandleFrameAnalysis): The candles, ready for tradingmachine's analysis methods.
            parameters (dict[str, float]): "period".

        Returns:
            dict[str, numpy.ndarray]: "adx", "plus" and "minus".
        """
        period = int(parameters['period'])
        adx_frame = analysis.average_directional_movement_index(window=period)
        plus_frame = analysis.plus_directional_indicator(window=period)
        minus_frame = analysis.minus_directional_indicator(window=period)
        return {
            'adx': self.column(adx_frame, f'adx_{period}'),
            'plus': self.column(plus_frame, f'plus_di_{period}'),
            'minus': self.column(minus_frame, f'minus_di_{period}'),
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
        analysis: candle_frame_analysis.CandleFrameAnalysis,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the two Aroon lines with tradingmachine.

        Args:
            analysis (candle_frame_analysis.CandleFrameAnalysis): The candles, ready for tradingmachine's analysis methods.
            parameters (dict[str, float]): "period".

        Returns:
            dict[str, numpy.ndarray]: "up" and "down".
        """
        period = int(parameters['period'])
        frame = analysis.aroon(window=period)
        return {
            'up': self.column(frame, f'aroon_up_{period}'),
            'down': self.column(frame, f'aroon_down_{period}'),
        }
