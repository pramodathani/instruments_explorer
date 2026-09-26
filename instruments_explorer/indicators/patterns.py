"""Candlestick patterns, shown as flags on the candles where they appear.

Typical usage example:

  values = CandlestickPatterns().compute(analysis, {})
"""

import numpy
from tradingmachine.assets.analysis import candle_frame_analysis

from instruments_explorer.indicators import base

PATTERN_LABELS = {
    'doji': 'Doji',
    'hammer': 'Hammer',
    'shooting_star': 'Shooting star',
    'engulfing': 'Engulfing',
    'harami': 'Harami',
    'morning_star': 'Morning star',
    'evening_star': 'Evening star',
    'three_white_soldiers': 'Three white soldiers',
    'three_black_crows': 'Three black crows',
}


class CandlestickPatterns(base.BaseIndicator):
    """Nine well-known candlestick patterns, found by TA-Lib through tradingmachine."""

    def __init__(self):
        """Describes the indicator."""
        outputs = []
        for pattern_key, pattern_label in PATTERN_LABELS.items():
            outputs.append(
                (
                    pattern_key,
                    pattern_label,
                )
            )
        super().__init__(
            key='patterns',
            short_label='Patterns',
            label='Candlestick patterns',
            family='Patterns',
            description='Flags on the candles where TA-Lib finds a doji, hammer, engulfing, star or similar pattern; green is bullish and red bearish.',
            placement='markers',
            parameters=[],
            outputs=outputs,
        )

    def compute(
        self,
        analysis: candle_frame_analysis.CandleFrameAnalysis,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Finds every pattern with tradingmachine.

        Args:
            analysis (candle_frame_analysis.CandleFrameAnalysis): The candles, ready for tradingmachine's analysis methods.
            parameters (dict[str, float]): None are used.

        Returns:
            dict[str, numpy.ndarray]: One array per pattern: 100 where a bullish pattern ends, −100 where a bearish one ends, and 0 elsewhere.
        """
        del parameters
        return {
            'doji': self.column(analysis.candle_doji(), 'candle_doji'),
            'hammer': self.column(analysis.candle_hammer(), 'candle_hammer'),
            'shooting_star': self.column(
                analysis.candle_shooting_star(),
                'candle_shooting_star',
            ),
            'engulfing': self.column(
                analysis.candle_engulfing(),
                'candle_engulfing',
            ),
            'harami': self.column(analysis.candle_harami(), 'candle_harami'),
            'morning_star': self.column(
                analysis.candle_morning_star(),
                'candle_morning_star',
            ),
            'evening_star': self.column(
                analysis.candle_evening_star(),
                'candle_evening_star',
            ),
            'three_white_soldiers': self.column(
                analysis.candle_three_white_soldiers(),
                'candle_three_white_soldiers',
            ),
            'three_black_crows': self.column(
                analysis.candle_three_black_crows(),
                'candle_three_black_crows',
            ),
        }
