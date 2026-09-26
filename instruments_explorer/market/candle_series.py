"""An instrument's candles as number arrays, ready for TA-Lib and for the browser.

Typical usage example:

  series = CandleSeries.from_prices_document(document)
  rows = series.rows()
"""

import datetime
from collections.abc import Mapping, Sequence
from typing import Any, Self

import numpy

_PRICE_COLUMNS = [
    'open',
    'high',
    'low',
    'close',
    'volume',
    'oi',
]


class CandleSeries:
    """Candles held column by column, with times in epoch milliseconds and missing values as NaN.

    Attributes:
        times: The start of each candle, in epoch milliseconds.
        open: Opening prices.
        high: High prices.
        low: Low prices.
        close: Closing prices.
        volume: Traded volumes, NaN where unknown.
        oi: Open interest, NaN where unknown.
    """

    def __init__(
        self,
        times: list[int],
        columns: Mapping[str, numpy.ndarray],
    ):
        """Creates the series from its columns.

        Args:
            times (list[int]): The start of each candle, in epoch milliseconds.
            columns (Mapping[str, numpy.ndarray]): One float64 array per name in open, high, low, close, volume and oi.
        """
        self.times = times
        self.open = columns['open']
        self.high = columns['high']
        self.low = columns['low']
        self.close = columns['close']
        self.volume = columns['volume']
        self.oi = columns['oi']

    @classmethod
    def from_prices_document(cls, document: Mapping[str, Any]) -> Self:
        """Reads UBI's prices answer, skipping any candle without a time or a close.

        Args:
            document (Mapping[str, Any]): UBI's answer, with "columns" and "candles".

        Returns:
            Self: The series, oldest candle first.

        Raises:
            ValueError: A candle's time is not an ISO 8601 date and time.
        """
        names = list(document.get('columns') or [])
        positions = {}
        for position, name in enumerate(names):
            positions[name] = position
        times = []
        values = {}
        for column in _PRICE_COLUMNS:
            values[column] = []
        for candle in document.get('candles') or []:
            time_text = cls._cell(candle, positions, 'time')
            close = cls._cell(candle, positions, 'close')
            if time_text is None or close is None:
                continue
            moment = datetime.datetime.fromisoformat(str(time_text))
            times.append(int(moment.timestamp() * 1000))
            for column in _PRICE_COLUMNS:
                value = cls._cell(candle, positions, column)
                values[column].append(numpy.nan if value is None else value)
        columns = {}
        for column in _PRICE_COLUMNS:
            columns[column] = numpy.array(values[column], dtype=numpy.float64)
        return cls(times, columns)

    def __len__(self) -> int:
        """Counts the candles.

        Returns:
            int: The number of candles.
        """
        return len(self.times)

    def since(self, first_time: int) -> Self:
        """Keeps only the candles that start at or after a moment.

        Args:
            first_time (int): The earliest candle start to keep, in epoch milliseconds.

        Returns:
            Self: A new series holding the later candles.
        """
        start = 0
        while start < len(self.times) and self.times[start] < first_time:
            start += 1
        columns = {
            'open': self.open[start:],
            'high': self.high[start:],
            'low': self.low[start:],
            'close': self.close[start:],
            'volume': self.volume[start:],
            'oi': self.oi[start:],
        }
        return type(self)(self.times[start:], columns)

    def rows(self) -> list[list[Any]]:
        """Writes the candles as compact rows for the browser.

        Returns:
            list[list[Any]]: One [time, open, high, low, close, volume, oi] row per candle, with None for missing values.
        """
        rows = []
        for index, time in enumerate(self.times):
            row = [
                time,
            ]
            for column in [
                self.open,
                self.high,
                self.low,
                self.close,
                self.volume,
                self.oi,
            ]:
                value = column[index]
                row.append(None if numpy.isnan(value) else float(value))
            rows.append(row)
        return rows

    def has_volume(self) -> bool:
        """Says whether any candle has a volume above zero.

        Returns:
            bool: False for series such as indices, whose volume is always zero or missing.
        """
        return bool(numpy.nansum(self.volume) > 0)

    @staticmethod
    def _cell(
        candle: Sequence[Any],
        positions: Mapping[str, int],
        name: str,
    ) -> Any:
        """Reads one named cell of a candle row.

        Args:
            candle (Sequence[Any]): The row.
            positions (Mapping[str, int]): The position of each column name.
            name (str): The column to read.

        Returns:
            Any: The value, or None when the column is absent.
        """
        position = positions.get(name)
        if position is None or position >= len(candle):
            return None
        return candle[position]
