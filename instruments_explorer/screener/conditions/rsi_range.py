"""Finds stocks whose 14-day RSI lies in a range, such as below 30 for oversold.

Typical usage example:

  RsiRange().matches(figures, {'minimum': 0, 'maximum': 30})
"""

from collections.abc import Mapping
from typing import Any

from instruments_explorer.indicators import base as indicator_base
from instruments_explorer.screener.conditions import base


class RsiRange(base.BaseCondition):
    """RSI between two levels."""

    def __init__(self):
        """Describes the condition."""
        super().__init__(
            key='rsi',
            label='RSI between',
            description='The 14-day RSI lies in a range; below 30 is often read as oversold and above 70 as overbought.',
            parameters=[
                indicator_base.IndicatorParameter('minimum', 'From', 0, 0, 100),
                indicator_base.IndicatorParameter('maximum', 'To', 30, 0, 100),
            ],
        )

    def matches(
        self,
        figures: Mapping[str, Any],
        parameters: Mapping[str, float],
    ) -> bool:
        """Tests the RSI.

        Args:
            figures (Mapping[str, Any]): The stock's figures.
            parameters (Mapping[str, float]): "minimum" and "maximum".

        Returns:
            bool: Whether the RSI lies in the range.
        """
        return self.between(
            figures.get('rsi_14'),
            parameters['minimum'],
            parameters['maximum'],
        )
