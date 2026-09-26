"""Finds stocks whose 50-day average recently crossed below their 200-day average.

Typical usage example:

  DeathCross().matches(figures, {'within': 10})
"""

from collections.abc import Mapping
from typing import Any

from instruments_explorer.indicators import base as indicator_base
from instruments_explorer.screener.conditions import base


class DeathCross(base.BaseCondition):
    """The 50-day average crossed below the 200-day within a number of days."""

    def __init__(self):
        """Describes the condition."""
        super().__init__(
            key='death_cross',
            label='Death cross',
            description='The 50-day average crossed below the 200-day average recently, a classic sign of a trend turning down.',
            parameters=[
                indicator_base.IndicatorParameter(
                    'within', 'Within days', 10, 0, 20
                ),
            ],
        )

    def matches(
        self,
        figures: Mapping[str, Any],
        parameters: Mapping[str, float],
    ) -> bool:
        """Tests how long ago the cross happened.

        Args:
            figures (Mapping[str, Any]): The stock's figures.
            parameters (Mapping[str, float]): "within".

        Returns:
            bool: Whether the cross happened within the days given.
        """
        return self.between(
            figures.get('death_cross_days'), 0, parameters['within']
        )
