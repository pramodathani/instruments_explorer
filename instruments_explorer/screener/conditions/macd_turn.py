"""Finds stocks whose MACD line recently crossed above its signal line.

Typical usage example:

  MacdTurn().matches(figures, {'within': 5})
"""

from collections.abc import Mapping
from typing import Any

from instruments_explorer.indicators import base as indicator_base
from instruments_explorer.screener.conditions import base


class MacdTurn(base.BaseCondition):
    """MACD crossed above its signal line within a number of days."""

    def __init__(self):
        """Describes the condition."""
        super().__init__(
            key='macd_turn',
            label='MACD turning up',
            description='The MACD line (12, 26, 9) crossed above its signal line recently, often read as momentum turning up.',
            parameters=[
                indicator_base.IndicatorParameter(
                    'within', 'Within days', 5, 0, 20
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
            figures.get('macd_cross_days'), 0, parameters['within']
        )
