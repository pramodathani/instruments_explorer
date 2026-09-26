"""Candlestick patterns, shown as flags on the candles where they appear.

Typical usage example:

  values = CandlestickPatterns().compute(series, {})
"""

import numpy
import talib

from instruments_explorer.indicators import base
from instruments_explorer.market import candle_series

PATTERN_FUNCTIONS = {
    'doji': talib.CDLDOJI,
    'hammer': talib.CDLHAMMER,
    'shooting_star': talib.CDLSHOOTINGSTAR,
    'engulfing': talib.CDLENGULFING,
    'harami': talib.CDLHARAMI,
    'morning_star': talib.CDLMORNINGSTAR,
    'evening_star': talib.CDLEVENINGSTAR,
    'three_white_soldiers': talib.CDL3WHITESOLDIERS,
    'three_black_crows': talib.CDL3BLACKCROWS,
}
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
    """Nine well-known candlestick patterns found by TA-Lib."""

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
        series: candle_series.CandleSeries,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Finds every pattern.

        Args:
            series (candle_series.CandleSeries): The candles.
            parameters (dict[str, float]): None are used.

        Returns:
            dict[str, numpy.ndarray]: One array per pattern: 100 where a bullish pattern ends, −100 where a bearish one ends, and 0 elsewhere.
        """
        del parameters
        found = {}
        for pattern_key, function in PATTERN_FUNCTIONS.items():
            values = function(
                series.open, series.high, series.low, series.close
            )
            found[pattern_key] = values.astype(numpy.float64)
        return found
