"""The shared shape of every screening condition.

Each condition is its own class in its own file. This base holds only what they share: describing the condition, checking its parameters (with the indicators' parameter class), and naming a configured use of it.

Typical usage example:

  condition = rsi_range.RsiRange()
  parameters = condition.resolve(['0', '30'])
  if condition.matches(figures, parameters):
      ...
"""

from collections.abc import Mapping, Sequence
from typing import Any

from instruments_explorer.indicators import base as indicator_base


class BaseCondition:
    """What every condition has; subclasses decide whether a stock matches.

    Attributes:
        key: The short name used in requests, such as "rsi".
        label: The name shown to people.
        description: One sentence on what the condition finds.
        parameters: The numbers it can be tuned by, in request order.
    """

    def __init__(
        self,
        key: str,
        label: str,
        description: str,
        parameters: Sequence[indicator_base.IndicatorParameter],
    ):
        """Creates the condition's description.

        Args:
            key (str): The short name used in requests.
            label (str): The name shown to people.
            description (str): One sentence on what the condition finds.
            parameters (Sequence[indicator_base.IndicatorParameter]): The numbers it can be tuned by, in request order.
        """
        self.key = key
        self.label = label
        self.description = description
        self.parameters = list(parameters)

    def describe(self) -> dict[str, Any]:
        """Describes the condition for the browser's condition picker.

        Returns:
            dict[str, Any]: "key", "label", "description" and "parameters".
        """
        parameters = []
        for parameter in self.parameters:
            parameters.append(parameter.describe())
        return {
            'key': self.key,
            'label': self.label,
            'description': self.description,
            'parameters': parameters,
        }

    def resolve(self, values: Sequence[str]) -> dict[str, float]:
        """Checks the parameter values a request gives, filling in defaults for any left out.

        Args:
            values (Sequence[str]): The values in parameter order.

        Returns:
            dict[str, float]: Every parameter's value by name.

        Raises:
            ValueError: There are more values than parameters, or a value is invalid.
        """
        if len(values) > len(self.parameters):
            raise ValueError(
                f'{self.label} takes at most {len(self.parameters)} parameters, not {len(values)}.'
            )
        resolved = {}
        for position, parameter in enumerate(self.parameters):
            if position < len(values) and values[position] != '':
                resolved[parameter.name] = parameter.parse(values[position])
            else:
                resolved[parameter.name] = parameter.default
        return resolved

    def matches(
        self,
        figures: Mapping[str, Any],
        parameters: Mapping[str, float],
    ) -> bool:
        """Says whether a stock's figures meet the condition.

        Args:
            figures (Mapping[str, Any]): The stock's figures from StockMetrics.
            parameters (Mapping[str, float]): The resolved parameters.

        Returns:
            bool: True when the stock matches; False when it does not or a figure it needs is missing.

        Raises:
            NotImplementedError: A subclass did not define the test.
        """
        raise NotImplementedError

    def between(self, value: Any, minimum: float, maximum: float) -> bool:
        """Checks that a figure exists and lies in a range.

        Args:
            value (Any): The figure, or None.
            minimum (float): The lowest value allowed.
            maximum (float): The highest value allowed.

        Returns:
            bool: True when the figure is a number from minimum to maximum.
        """
        return value is not None and minimum <= value <= maximum
