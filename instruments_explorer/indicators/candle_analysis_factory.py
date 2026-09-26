"""Turns a CandleSeries into tradingmachine's analysis object, so every indicator can be computed from one set of candles.

Typical usage example:

  analysis = CandleAnalysisFactory().create(series)
  frame = analysis.relative_strength_index(window=14)
"""

import numpy
import pandas
from tradingmachine.assets.analysis import candle_frame_analysis

from instruments_explorer.market import candle_series


class CandleAnalysisFactory:
    """Builds tradingmachine's candle analysis over an instrument's candles."""

    def create(
        self,
        series: candle_series.CandleSeries,
    ) -> candle_frame_analysis.CandleFrameAnalysis:
        """Builds the analysis over the candles, with missing volume counted as zero.

        Args:
            series (candle_series.CandleSeries): The candles, oldest first.

        Returns:
            candle_frame_analysis.CandleFrameAnalysis: The analysis, whose rows line up one to one with the series' candles.
        """
        frame = pandas.DataFrame(
            {
                'open': series.open,
                'high': series.high,
                'low': series.low,
                'close': series.close,
                'volume': numpy.nan_to_num(series.volume),
                'oi': series.oi,
            }
        )
        return candle_frame_analysis.CandleFrameAnalysis(frame)
