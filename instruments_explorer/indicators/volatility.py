"""Volatility indicators: how widely the price is swinging.

Typical usage example:

  values = BollingerBands().compute(analysis, {'period': 20, 'deviations': 2.0})
"""

import numpy
from tradingmachine.assets.analysis import candle_frame_analysis

from instruments_explorer.indicators import base

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
        analysis: candle_frame_analysis.CandleFrameAnalysis,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the three bands with tradingmachine.

        Args:
            analysis (candle_frame_analysis.CandleFrameAnalysis): The candles, ready for tradingmachine's analysis methods.
            parameters (dict[str, float]): "period" and "deviations".

        Returns:
            dict[str, numpy.ndarray]: "upper", "middle" and "lower".
        """
        period = int(parameters['period'])
        frame = analysis.bollinger_bands(
            window=period,
            standard_deviations_up=parameters['deviations'],
            standard_deviations_down=parameters['deviations'],
        )
        return {
            'upper': self.column(frame, f'bb_upper_{period}'),
            'middle': self.column(frame, f'bb_middle_{period}'),
            'lower': self.column(frame, f'bb_lower_{period}'),
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
        analysis: candle_frame_analysis.CandleFrameAnalysis,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the average true range with tradingmachine.

        Args:
            analysis (candle_frame_analysis.CandleFrameAnalysis): The candles, ready for tradingmachine's analysis methods.
            parameters (dict[str, float]): "period".

        Returns:
            dict[str, numpy.ndarray]: "value".
        """
        period = int(parameters['period'])
        frame = analysis.average_true_range(window=period)
        return {
            'value': self.column(frame, f'atr_{period}'),
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
        analysis: candle_frame_analysis.CandleFrameAnalysis,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the normalized average true range with tradingmachine.

        Args:
            analysis (candle_frame_analysis.CandleFrameAnalysis): The candles, ready for tradingmachine's analysis methods.
            parameters (dict[str, float]): "period".

        Returns:
            dict[str, numpy.ndarray]: "value".
        """
        period = int(parameters['period'])
        frame = analysis.normalized_average_true_range(window=period)
        return {
            'value': self.column(frame, f'natr{period}'),
        }
