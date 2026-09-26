"""Works out the figures a stock screen tests, from a stock's daily candles.

Typical usage example:

  metrics = StockMetrics().compute(series)
"""

import datetime
from typing import Any

import numpy
import talib

from instruments_explorer.market import candle_series

MINIMUM_CANDLES = 30
CROSS_LOOKBACK = 20
RETURN_PERIODS = [
    1,
    5,
    21,
    63,
    252,
]
_TRADING_DAYS_PER_YEAR = 252
_INDIA = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


class StockMetrics:
    """Computes returns, ranges, averages, crossovers, momentum, trend strength and volume figures for one stock."""

    def compute(
        self, series: candle_series.CandleSeries
    ) -> dict[str, Any] | None:
        """Works out every figure from the latest candle's point of view.

        Args:
            series (candle_series.CandleSeries): The stock's daily candles, oldest first.

        Returns:
            dict[str, Any] | None: The figures, with None where the history is too short for one; None for the whole result when there are fewer than MINIMUM_CANDLES candles.
        """
        if len(series) < MINIMUM_CANDLES:
            return None
        close = series.close
        last = len(close) - 1
        figures = {
            'close': self._number(close[last]),
            'candles': len(close),
            'last_candle_date': datetime.datetime.fromtimestamp(
                series.times[last] / 1000,
                tz=_INDIA,
            )
            .date()
            .isoformat(),
        }
        for days in RETURN_PERIODS:
            figures[f'change_{days}d'] = self._change(close, days)
        high = float(numpy.nanmax(series.high[-_TRADING_DAYS_PER_YEAR:]))
        low = float(numpy.nanmin(series.low[-_TRADING_DAYS_PER_YEAR:]))
        figures['high_52w'] = high
        figures['low_52w'] = low
        figures['from_high'] = self._percent(close[last], high)
        figures['from_low'] = self._percent(close[last], low)
        averages = {}
        for period in [
            20,
            50,
            200,
        ]:
            average = talib.SMA(close, timeperiod=period)
            averages[period] = average
            figures[f'sma_{period}'] = self._number(average[last])
            figures[f'above_sma_{period}'] = self._above(
                close[last], average[last]
            )
        figures['ema_20'] = self._number(talib.EMA(close, timeperiod=20)[last])
        figures['rsi_14'] = self._number(talib.RSI(close, timeperiod=14)[last])
        figures['golden_cross_days'] = self._days_since_cross(
            averages[50], averages[200], upward=True
        )
        figures['death_cross_days'] = self._days_since_cross(
            averages[50], averages[200], upward=False
        )
        macd, signal, histogram = talib.MACD(close, 12, 26, 9)
        figures['macd'] = self._number(macd[last])
        figures['macd_signal'] = self._number(signal[last])
        figures['macd_histogram'] = self._number(histogram[last])
        figures['macd_cross_days'] = self._days_since_cross(
            macd, signal, upward=True
        )
        figures['adx_14'] = self._number(
            talib.ADX(series.high, series.low, close, timeperiod=14)[last]
        )
        figures['natr_14'] = self._number(
            talib.NATR(series.high, series.low, close, timeperiod=14)[last]
        )
        upper, _, lower = talib.BBANDS(
            close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0
        )
        width = upper[last] - lower[last]
        figures['percent_b'] = None
        if not numpy.isnan(width) and width > 0:
            figures['percent_b'] = round(
                float((close[last] - lower[last]) / width), 4
            )
        volume = numpy.nan_to_num(series.volume)
        average_volume = (
            float(numpy.mean(volume[-21:-1])) if len(volume) > 21 else None
        )
        figures['volume'] = float(volume[last])
        figures['average_volume_20'] = average_volume
        figures['volume_ratio'] = None
        figures['traded_value'] = None
        if average_volume:
            figures['volume_ratio'] = round(
                float(volume[last]) / average_volume, 3
            )
            figures['traded_value'] = round(
                float(close[last]) * average_volume, 2
            )
        return figures

    def _change(self, close: numpy.ndarray, days: int) -> float | None:
        """Works out the percentage change over a number of candles.

        Args:
            close (numpy.ndarray): Closing prices.
            days (int): How many candles back.

        Returns:
            float | None: The change in percent, or None when the history is shorter.
        """
        if len(close) <= days:
            return None
        return self._percent(close[-1], close[-1 - days])

    def _percent(self, value: float, base: float) -> float | None:
        """Works out how far a value is from a base, in percent.

        Args:
            value (float): The value.
            base (float): The base.

        Returns:
            float | None: The difference in percent of the base, or None when the base is zero or missing.
        """
        if base is None or numpy.isnan(base) or base == 0:
            return None
        return round(float((value / base - 1.0) * 100.0), 4)

    def _above(self, value: float, average: float) -> bool | None:
        """Says whether a price is above an average.

        Args:
            value (float): The price.
            average (float): The average, NaN when the history is too short.

        Returns:
            bool | None: The answer, or None without an average.
        """
        if numpy.isnan(average):
            return None
        return bool(value > average)

    def _days_since_cross(
        self,
        fast: numpy.ndarray,
        slow: numpy.ndarray,
        upward: bool,
    ) -> int | None:
        """Finds how many candles ago one line last crossed another, within CROSS_LOOKBACK candles.

        Args:
            fast (numpy.ndarray): The line that crosses.
            slow (numpy.ndarray): The line it crosses.
            upward (bool): True to find the fast line crossing above, False below.

        Returns:
            int | None: 0 when it crossed on the latest candle, or None when it did not cross within the lookback.
        """
        last = len(fast) - 1
        for index in range(last, max(last - CROSS_LOOKBACK, 0), -1):
            before = fast[index - 1] - slow[index - 1]
            after = fast[index] - slow[index]
            if numpy.isnan(before) or numpy.isnan(after):
                return None
            if upward and before <= 0 < after:
                return last - index
            if not upward and before >= 0 > after:
                return last - index
        return None

    def _number(self, value: float) -> float | None:
        """Turns a TA-Lib value into a stored number.

        Args:
            value (float): The value, NaN when there is none yet.

        Returns:
            float | None: The value rounded to four places, or None.
        """
        if value is None or numpy.isnan(value):
            return None
        return round(float(value), 4)
