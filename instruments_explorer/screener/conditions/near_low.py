"""Finds stocks trading close to their 52-week low.

Typical usage example:

  NearLow().matches(figures, {'within': 5})
"""

from collections.abc import Mapping
from typing import Any

from instruments_explorer.indicators import base as indicator_base
from instruments_explorer.screener.conditions import base


class NearLow(base.BaseCondition):
    """The close within a percentage of the 52-week low."""

    def __init__(self):
        """Describes the condition."""
        super().__init__(
            key='near_low',
            label='Near 52-week low',
            description='The latest close is within a few percent of the lowest price of the past year.',
            parameters=[
                indicator_base.IndicatorParameter(
                    'within', 'Within %', 5, 0, 1000, whole_number=False
                ),
            ],
        )

    def matches(
        self,
        figures: Mapping[str, Any],
        parameters: Mapping[str, float],
    ) -> bool:
        """Tests the distance from the low.

        Args:
            figures (Mapping[str, Any]): The stock's figures.
            parameters (Mapping[str, float]): "within".

        Returns:
            bool: Whether the close is within the percentage of the low.
        """
        return self.between(figures.get('from_low'), 0, parameters['within'])
