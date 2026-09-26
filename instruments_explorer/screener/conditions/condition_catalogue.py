"""The list of screening conditions the screener offers.

Typical usage example:

  condition = ConditionCatalogue().find('rsi')
"""

from typing import Any

from instruments_explorer.screener.conditions import above_average
from instruments_explorer.screener.conditions import base
from instruments_explorer.screener.conditions import below_average
from instruments_explorer.screener.conditions import death_cross
from instruments_explorer.screener.conditions import golden_cross
from instruments_explorer.screener.conditions import macd_turn
from instruments_explorer.screener.conditions import near_high
from instruments_explorer.screener.conditions import near_low
from instruments_explorer.screener.conditions import return_range
from instruments_explorer.screener.conditions import rsi_range
from instruments_explorer.screener.conditions import strong_trend
from instruments_explorer.screener.conditions import volume_spike


class ConditionCatalogue:
    """Every condition, in the order the picker lists them."""

    def __init__(self):
        """Creates one instance of every condition."""
        self._conditions = [
            rsi_range.RsiRange(),
            return_range.ReturnRange(),
            above_average.AboveAverage(),
            below_average.BelowAverage(),
            golden_cross.GoldenCross(),
            death_cross.DeathCross(),
            macd_turn.MacdTurn(),
            near_high.NearHigh(),
            near_low.NearLow(),
            volume_spike.VolumeSpike(),
            strong_trend.StrongTrend(),
        ]
        self._by_key = {}
        for condition in self._conditions:
            self._by_key[condition.key] = condition

    def find(self, key: str) -> base.BaseCondition:
        """Finds a condition by its key.

        Args:
            key (str): The key, such as "rsi".

        Returns:
            base.BaseCondition: The condition.

        Raises:
            ValueError: No condition has that key.
        """
        condition = self._by_key.get(key)
        if condition is None:
            raise ValueError(f'Unknown screening condition: {key!r}')
        return condition

    def describe(self) -> list[dict[str, Any]]:
        """Describes every condition for the browser's picker.

        Returns:
            list[dict[str, Any]]: One description per condition, in picker order.
        """
        descriptions = []
        for condition in self._conditions:
            descriptions.append(condition.describe())
        return descriptions
