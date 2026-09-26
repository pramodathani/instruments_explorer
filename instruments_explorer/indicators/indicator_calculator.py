"""Computes the indicators a chart asks for and shapes them for Highcharts.

A chart asks for each indicator as text: the indicator's key followed by its parameters, separated by colons, such as "sma:50", "bbands:20:2" or "macd:12:26:9". Parameters left out take their defaults.

Typical usage example:

  calculator = IndicatorCalculator(IndicatorCatalogue())
  results, errors = calculator.compute(series, ['sma:50', 'rsi:14'])
"""

from collections.abc import Sequence
from typing import Any

import numpy
from tradingmachine.assets.analysis import candle_frame_analysis

from instruments_explorer.indicators import candle_analysis_factory
from instruments_explorer.indicators import indicator_catalogue
from instruments_explorer.indicators import patterns
from instruments_explorer.market import candle_series

MAXIMUM_INDICATORS = 12


class IndicatorCalculator:
    """Turns indicator requests into lines and markers aligned with the candles."""

    def __init__(self, catalogue: indicator_catalogue.IndicatorCatalogue):
        """Creates the calculator.

        Args:
            catalogue (indicator_catalogue.IndicatorCatalogue): Finds indicators by key.
        """
        self._catalogue = catalogue
        self._factory = candle_analysis_factory.CandleAnalysisFactory()

    def compute(
        self,
        series: candle_series.CandleSeries,
        requests: Sequence[str],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Computes every requested indicator from one tradingmachine analysis of the candles, collecting a message for each one that cannot be computed.

        Args:
            series (candle_series.CandleSeries): The candles.
            requests (Sequence[str]): Indicator requests such as "rsi:14".

        Returns:
            tuple[list[dict[str, Any]], list[str]]: A tuple (one result per computed indicator, one message per request that failed).
        """
        results = []
        errors = []
        if len(requests) > MAXIMUM_INDICATORS:
            errors.append(
                f'At most {MAXIMUM_INDICATORS} indicators can be shown at once; the rest were left out.'
            )
            requests = requests[:MAXIMUM_INDICATORS]
        analysis = self._factory.create(series)
        for request in requests:
            try:
                results.append(self._compute_one(series, analysis, request))
            except ValueError as error:
                errors.append(str(error))
        return results, errors

    def warm_up_candles(self, requests: Sequence[str]) -> int:
        """Finds the longest warm-up any valid request needs.

        Args:
            requests (Sequence[str]): Indicator requests such as "rsi:14"; invalid ones are ignored here and reported by compute.

        Returns:
            int: The number of extra candles to read before the chart's first candle.
        """
        longest = 0
        for request in requests[:MAXIMUM_INDICATORS]:
            pieces = request.strip().lower().split(':')
            try:
                indicator = self._catalogue.find(pieces[0])
                parameters = indicator.resolve(pieces[1:])
            except ValueError:
                continue
            longest = max(longest, indicator.warm_up_candles(parameters))
        return longest

    def _compute_one(
        self,
        series: candle_series.CandleSeries,
        analysis: candle_frame_analysis.CandleFrameAnalysis,
        request: str,
    ) -> dict[str, Any]:
        """Computes one requested indicator.

        Args:
            series (candle_series.CandleSeries): The candles.
            analysis (candle_frame_analysis.CandleFrameAnalysis): The same candles, ready for tradingmachine's analysis methods.
            request (str): The request, such as "bbands:20:2".

        Returns:
            dict[str, Any]: "id", "key", "title", "placement", "reference_lines", "outputs" (each with "key", "label" and "points") and "markers".

        Raises:
            ValueError: The request names an unknown indicator, has invalid parameters, or needs volume the instrument does not have.
        """
        pieces = request.strip().lower().split(':')
        indicator = self._catalogue.find(pieces[0])
        parameters = indicator.resolve(pieces[1:])
        if indicator.needs_volume and not series.has_volume():
            raise ValueError(
                f'{indicator.label} needs volume, and this instrument has none.'
            )
        values = indicator.compute(analysis, parameters)
        outputs = []
        markers = []
        if indicator.placement == 'markers':
            markers = self._markers(series, values)
        else:
            for output_key, output_label in indicator.outputs:
                outputs.append(
                    {
                        'key': output_key,
                        'label': output_label,
                        'points': self._points(series, values[output_key]),
                    }
                )
        return {
            'id': request.strip().lower(),
            'key': indicator.key,
            'title': indicator.title(parameters),
            'placement': indicator.placement,
            'reference_lines': indicator.reference_lines,
            'outputs': outputs,
            'markers': markers,
        }

    def _points(
        self,
        series: candle_series.CandleSeries,
        values: numpy.ndarray,
    ) -> list[list[float]]:
        """Pairs each value with its candle's time, leaving out the NaN values before the indicator has enough history.

        Args:
            series (candle_series.CandleSeries): The candles.
            values (numpy.ndarray): The indicator's values, one per candle.

        Returns:
            list[list[float]]: [time, value] pairs.
        """
        points = []
        for index, time in enumerate(series.times):
            value = values[index]
            if numpy.isnan(value):
                continue
            points.append(
                [
                    time,
                    round(float(value), 6),
                ]
            )
        return points

    def _markers(
        self,
        series: candle_series.CandleSeries,
        values: dict[str, numpy.ndarray],
    ) -> list[dict[str, Any]]:
        """Lists the candles where a pattern was found.

        Args:
            series (candle_series.CandleSeries): The candles.
            values (dict[str, numpy.ndarray]): One array per pattern, nonzero where it was found.

        Returns:
            list[dict[str, Any]]: One {"time", "pattern", "label", "bullish"} per finding, oldest first.
        """
        markers = []
        for pattern_key, found in values.items():
            for index, time in enumerate(series.times):
                value = found[index]
                if numpy.isnan(value) or value == 0:
                    continue
                markers.append(
                    {
                        'time': time,
                        'pattern': pattern_key,
                        'label': patterns.PATTERN_LABELS[pattern_key],
                        'bullish': bool(value > 0),
                    }
                )
        markers.sort(key=lambda marker: marker['time'])
        return markers
