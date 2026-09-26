"""Finds stocks whose return over a period lies in a range.

Typical usage example:

  ReturnRange().matches(figures, {'days': 21, 'minimum': 10, 'maximum': 1000})
"""

from collections.abc import Mapping
from typing import Any

from instruments_explorer.indicators import base as indicator_base
from instruments_explorer.screener import stock_metrics
from instruments_explorer.screener.conditions import base


class ReturnRange(base.BaseCondition):
    """The percentage return over 1, 5, 21, 63 or 252 trading days between two values."""

    def __init__(self):
        """Describes the condition."""
        super().__init__(
            key='return',
            label='Return over a period',
            description='The percentage change over 1, 5, 21 (a month), 63 (a quarter) or 252 (a year) trading days lies in a range.',
            parameters=[
                indicator_base.IndicatorParameter(
                    'days', 'Trading days', 21, 1, 252
                ),
                indicator_base.IndicatorParameter(
                    'minimum', 'From %', 5, -100, 10000, whole_number=False
                ),
                indicator_base.IndicatorParameter(
                    'maximum', 'To %', 10000, -100, 10000, whole_number=False
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
            ValueError: A value is invalid, or the period is not 1, 5, 21, 63 or 252.
        """
        resolved = super().resolve(values)
        if resolved['days'] not in stock_metrics.RETURN_PERIODS:
            raise ValueError(
                f'The return period must be one of {stock_metrics.RETURN_PERIODS} trading days, not {resolved["days"]}.'
            )
        return resolved

    def matches(
        self,
        figures: Mapping[str, Any],
        parameters: Mapping[str, float],
    ) -> bool:
        """Tests the return.

        Args:
            figures (Mapping[str, Any]): The stock's figures.
            parameters (Mapping[str, float]): "days", "minimum" and "maximum".

        Returns:
            bool: Whether the return lies in the range.
        """
        return self.between(
            figures.get(f'change_{int(parameters["days"])}d'),
            parameters['minimum'],
            parameters['maximum'],
        )
