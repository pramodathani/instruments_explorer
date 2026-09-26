"""Finds stocks trading close to their 52-week high.

Typical usage example:

  NearHigh().matches(figures, {'within': 5})
"""

from collections.abc import Mapping
from typing import Any

from instruments_explorer.indicators import base as indicator_base
from instruments_explorer.screener.conditions import base


class NearHigh(base.BaseCondition):
    """The close within a percentage of the 52-week high."""

    def __init__(self):
        """Describes the condition."""
        super().__init__(
            key='near_high',
            label='Near 52-week high',
            description='The latest close is within a few percent of the highest price of the past year.',
            parameters=[
                indicator_base.IndicatorParameter(
                    'within', 'Within %', 5, 0, 100, whole_number=False
                ),
            ],
        )

    def matches(
        self,
        figures: Mapping[str, Any],
        parameters: Mapping[str, float],
    ) -> bool:
        """Tests the distance from the high.

        Args:
            figures (Mapping[str, Any]): The stock's figures.
            parameters (Mapping[str, float]): "within".

        Returns:
            bool: Whether the close is within the percentage of the high.
        """
        return self.between(figures.get('from_high'), -parameters['within'], 0)
