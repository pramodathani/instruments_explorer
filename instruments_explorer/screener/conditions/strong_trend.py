"""Finds stocks in a strong trend, whichever way it runs.

Typical usage example:

  StrongTrend().matches(figures, {'minimum': 25})
"""

from collections.abc import Mapping
from typing import Any

from instruments_explorer.indicators import base as indicator_base
from instruments_explorer.screener.conditions import base


class StrongTrend(base.BaseCondition):
    """The 14-day ADX at or above a level."""

    def __init__(self):
        """Describes the condition."""
        super().__init__(
            key='strong_trend',
            label='Strong trend',
            description='The 14-day average directional index is at or above a level; above 25 is usually read as a trend, up or down.',
            parameters=[
                indicator_base.IndicatorParameter(
                    'minimum', 'ADX at least', 25, 0, 100
                ),
            ],
        )

    def matches(
        self,
        figures: Mapping[str, Any],
        parameters: Mapping[str, float],
    ) -> bool:
        """Tests the ADX.

        Args:
            figures (Mapping[str, Any]): The stock's figures.
            parameters (Mapping[str, float]): "minimum".

        Returns:
            bool: Whether the ADX is at or above the level.
        """
        adx = figures.get('adx_14')
        return adx is not None and adx >= parameters['minimum']
