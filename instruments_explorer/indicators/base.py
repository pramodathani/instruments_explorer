"""The shared shape of every indicator: its name, parameters, outputs and where it is drawn.

Each indicator is its own class in its family's module. This base holds only what is the same for all of them: describing the indicator to the browser, checking the parameters a request gives, and reading a computed column out of tradingmachine's answer. The computing itself is done by tradingmachine's analysis methods.

Typical usage example:

  indicator = moving_averages.SimpleMovingAverage()
  parameters = indicator.resolve(['50'])
  values = indicator.compute(analysis, parameters)
"""

from collections.abc import Sequence
from typing import Any

import numpy
import pandas
from tradingmachine.assets.analysis import candle_frame_analysis

PLACEMENTS = [
    'price',
    'panel',
    'markers',
]


class IndicatorParameter:
    """One number an indicator can be tuned by, such as a period.

    Attributes:
        name: The parameter's name in the computation, such as "period".
        label: The parameter's name for people, such as "Period".
        default: The value used when a request leaves it out.
        minimum: The smallest value allowed.
        maximum: The largest value allowed.
        whole_number: Whether only whole numbers are allowed.
    """

    def __init__(
        self,
        name: str,
        label: str,
        default: float,
        minimum: float,
        maximum: float,
        whole_number: bool = True,
    ):
        """Creates the parameter.

        Args:
            name (str): The parameter's name in the computation.
            label (str): The parameter's name for people.
            default (float): The value used when a request leaves it out.
            minimum (float): The smallest value allowed.
            maximum (float): The largest value allowed.
            whole_number (bool): Whether only whole numbers are allowed.
        """
        self.name = name
        self.label = label
        self.default = default
        self.minimum = minimum
        self.maximum = maximum
        self.whole_number = whole_number

    def parse(self, text: str) -> float:
        """Reads and checks a value given as text.

        Args:
            text (str): The value, such as "14" or "2.5".

        Returns:
            float: The value, an int when the parameter takes whole numbers.

        Raises:
            ValueError: The text is not a number, not a whole number when one is needed, or out of range.
        """
        try:
            value = float(text)
        except ValueError as error:
            raise ValueError(
                f'{self.label} must be a number: {text!r}'
            ) from error
        if self.whole_number:
            if value != int(value):
                raise ValueError(
                    f'{self.label} must be a whole number: {text!r}'
                )
            value = int(value)
        if value < self.minimum or value > self.maximum:
            raise ValueError(
                f'{self.label} must be between {self.minimum} and {self.maximum}: {text!r}'
            )
        return value

    def describe(self) -> dict[str, Any]:
        """Describes the parameter for the browser's indicator picker.

        Returns:
            dict[str, Any]: "name", "label", "default", "minimum", "maximum" and "whole_number".
        """
        return {
            'name': self.name,
            'label': self.label,
            'default': self.default,
            'minimum': self.minimum,
            'maximum': self.maximum,
            'whole_number': self.whole_number,
        }


class BaseIndicator:
    """What every indicator has; subclasses add their parameters and computation.

    Attributes:
        key: The short name used in requests, such as "sma".
        short_label: The name shown on the chart, such as "SMA".
        label: The full name, such as "Simple moving average".
        family: The group the picker lists it under, such as "Moving averages".
        description: One sentence on what the indicator shows.
        placement: "price" to draw over the candles, "panel" for its own pane below, or "markers" for flags on candles.
        parameters: The numbers it can be tuned by, in request order.
        outputs: A list of tuples (key, label) naming each line it draws.
        reference_lines: Levels drawn across its panel, such as 30 and 70 for RSI.
        needs_volume: Whether it is meaningless without volume.
    """

    def __init__(
        self,
        key: str,
        short_label: str,
        label: str,
        family: str,
        description: str,
        placement: str,
        parameters: Sequence[IndicatorParameter],
        outputs: Sequence[tuple[str, str]],
        reference_lines: Sequence[float] = (),
        needs_volume: bool = False,
    ):
        """Creates the indicator's description.

        Args:
            key (str): The short name used in requests.
            short_label (str): The name shown on the chart.
            label (str): The full name.
            family (str): The group the picker lists it under.
            description (str): One sentence on what the indicator shows.
            placement (str): One of PLACEMENTS.
            parameters (Sequence[IndicatorParameter]): The numbers it can be tuned by, in request order.
            outputs (Sequence[tuple[str, str]]): A tuple (key, label) per line it draws.
            reference_lines (Sequence[float]): Levels drawn across its panel.
            needs_volume (bool): Whether it is meaningless without volume.

        Raises:
            ValueError: The placement is not one of PLACEMENTS.
        """
        if placement not in PLACEMENTS:
            raise ValueError(f'Unknown indicator placement: {placement!r}')
        self.key = key
        self.short_label = short_label
        self.label = label
        self.family = family
        self.description = description
        self.placement = placement
        self.parameters = list(parameters)
        self.outputs = list(outputs)
        self.reference_lines = list(reference_lines)
        self.needs_volume = needs_volume

    def describe(self) -> dict[str, Any]:
        """Describes the indicator for the browser's indicator picker.

        Returns:
            dict[str, Any]: The key, labels, family, description, placement, parameters, outputs, reference lines and whether it needs volume.
        """
        parameters = []
        for parameter in self.parameters:
            parameters.append(parameter.describe())
        outputs = []
        for output_key, output_label in self.outputs:
            outputs.append(
                {
                    'key': output_key,
                    'label': output_label,
                }
            )
        return {
            'key': self.key,
            'short_label': self.short_label,
            'label': self.label,
            'family': self.family,
            'description': self.description,
            'placement': self.placement,
            'parameters': parameters,
            'outputs': outputs,
            'reference_lines': self.reference_lines,
            'needs_volume': self.needs_volume,
        }

    def resolve(self, values: Sequence[str]) -> dict[str, float]:
        """Checks the parameter values a request gives, filling in defaults for any left out.

        Args:
            values (Sequence[str]): The values in parameter order; fewer than the parameters is allowed.

        Returns:
            dict[str, float]: Every parameter's value by name.

        Raises:
            ValueError: There are more values than parameters, or a value is invalid.
        """
        if len(values) > len(self.parameters):
            raise ValueError(
                f'{self.short_label} takes at most {len(self.parameters)} parameters, not {len(values)}.'
            )
        resolved = {}
        for position, parameter in enumerate(self.parameters):
            if position < len(values) and values[position] != '':
                resolved[parameter.name] = parameter.parse(values[position])
            else:
                resolved[parameter.name] = parameter.default
        return resolved

    def title(self, parameters: dict[str, float]) -> str:
        """Names one configured use of the indicator for the chart's legend.

        Args:
            parameters (dict[str, float]): The resolved parameters.

        Returns:
            str: The short label and parameter values, such as "SMA 50" or "BB 20, 2".
        """
        if not self.parameters:
            return self.short_label
        values = []
        for parameter in self.parameters:
            value = parameters[parameter.name]
            if value == int(value):
                values.append(str(int(value)))
            else:
                values.append(str(value))
        return f'{self.short_label} {", ".join(values)}'

    def warm_up_candles(self, parameters: dict[str, float]) -> int:
        """Estimates how many candles the indicator needs before its first reliable value.

        Adding up the whole-number parameters covers stacked look-backs, such as MACD's slow average followed by its signal average.

        Args:
            parameters (dict[str, float]): The resolved parameters.

        Returns:
            int: The number of candles, zero for an indicator without look-back periods.
        """
        total = 0
        for parameter in self.parameters:
            if parameter.whole_number:
                total += int(parameters[parameter.name])
        return total

    def column(
        self,
        frame: pandas.DataFrame | None,
        name: str,
    ) -> numpy.ndarray:
        """Reads one column that a tradingmachine analysis method added, as numbers.

        Args:
            frame (pandas.DataFrame | None): The analysis method's answer, or None when there were no candles.
            name (str): The column the method added, such as "sma_20".

        Returns:
            numpy.ndarray: The column as float64, one value per candle, or an empty array when there were no candles.
        """
        if frame is None:
            return numpy.array([], dtype=numpy.float64)
        return frame[name].to_numpy(dtype=numpy.float64)

    def compute(
        self,
        analysis: candle_frame_analysis.CandleFrameAnalysis,
        parameters: dict[str, float],
    ) -> dict[str, numpy.ndarray]:
        """Computes the indicator's lines over the candles with tradingmachine.

        Args:
            analysis (candle_frame_analysis.CandleFrameAnalysis): The candles, ready for tradingmachine's analysis methods.
            parameters (dict[str, float]): The resolved parameters.

        Returns:
            dict[str, numpy.ndarray]: One array per output key, as long as the series, with NaN where the indicator has no value yet.

        Raises:
            NotImplementedError: A subclass did not define the computation.
        """
        raise NotImplementedError
