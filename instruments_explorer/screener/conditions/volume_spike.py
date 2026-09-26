"""Finds stocks that traded much more than usual on the latest day.

Typical usage example:

  VolumeSpike().matches(figures, {'ratio': 2})
"""

from collections.abc import Mapping
from typing import Any

from instruments_explorer.indicators import base as indicator_base
from instruments_explorer.screener.conditions import base


class VolumeSpike(base.BaseCondition):
    """The latest volume at least a multiple of the 20-day average."""

    def __init__(self):
        """Describes the condition."""
        super().__init__(
            key='volume_spike',
            label='Volume spike',
            description='The latest day’s volume is at least a multiple of the average of the 20 days before it.',
            parameters=[
                indicator_base.IndicatorParameter(
                    'ratio', 'At least ×', 2, 1, 100, whole_number=False
                ),
            ],
        )

    def matches(
        self,
        figures: Mapping[str, Any],
        parameters: Mapping[str, float],
    ) -> bool:
        """Tests the volume ratio.

        Args:
            figures (Mapping[str, Any]): The stock's figures.
            parameters (Mapping[str, float]): "ratio".

        Returns:
            bool: Whether the ratio is at least the multiple given.
        """
        ratio = figures.get('volume_ratio')
        return ratio is not None and ratio >= parameters['ratio']
