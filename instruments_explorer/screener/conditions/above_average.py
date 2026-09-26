"""Finds stocks trading above a moving average.

Typical usage example:

  AboveAverage().matches(figures, {'period': 200})
"""

from collections.abc import Mapping
from typing import Any

from instruments_explorer.indicators import base as indicator_base
from instruments_explorer.screener.conditions import base

PERIODS = [
    20,
    50,
    200,
]


class AboveAverage(base.BaseCondition):
    """The close above its 20, 50 or 200-day simple moving average."""

    def __init__(self):
        """Describes the condition."""
        super().__init__(
            key='above_average',
            label='Above moving average',
            description='The latest close is above its 20, 50 or 200-day simple moving average; above the 200-day is a common sign of a long uptrend.',
            parameters=[
                indicator_base.IndicatorParameter(
                    'period', 'Days', 200, 20, 200
                ),
            ],
        )

    def resolve(self, values: list[str]) -> dict[str, float]:
        """Checks the parameters, and that the period is one the metrics hold.

        Args:
            values (list[str]): The values in parameter order.

        Returns:
            dict[str, float]: Every parameter's value by name.

        Raises:
            ValueError: A value is invalid, or the period is not 20, 50 or 200.
        """
        resolved = super().resolve(values)
        if resolved['period'] not in PERIODS:
            raise ValueError(
                f'The average must be one of {PERIODS} days, not {resolved["period"]}.'
            )
        return resolved

    def matches(
        self,
        figures: Mapping[str, Any],
        parameters: Mapping[str, float],
    ) -> bool:
        """Tests the close against the average.

        Args:
            figures (Mapping[str, Any]): The stock's figures.
            parameters (Mapping[str, float]): "period".

        Returns:
            bool: Whether the close is above the average.
        """
        return figures.get(f'above_sma_{int(parameters["period"])}') is True
