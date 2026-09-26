"""The list of indicators the explorer offers.

Typical usage example:

  catalogue = IndicatorCatalogue()
  indicator = catalogue.find('rsi')
"""

from typing import Any

from instruments_explorer.indicators import base
from instruments_explorer.indicators import momentum
from instruments_explorer.indicators import moving_averages
from instruments_explorer.indicators import patterns
from instruments_explorer.indicators import trend
from instruments_explorer.indicators import volatility
from instruments_explorer.indicators import volume


class IndicatorCatalogue:
    """Every indicator, in the order the picker lists them."""

    def __init__(self):
        """Creates one instance of every indicator."""
        self._indicators = [
            moving_averages.SimpleMovingAverage(),
            moving_averages.ExponentialMovingAverage(),
            moving_averages.WeightedMovingAverage(),
            moving_averages.DoubleExponentialMovingAverage(),
            moving_averages.TripleExponentialMovingAverage(),
            volatility.BollingerBands(),
            volatility.AverageTrueRange(),
            volatility.NormalizedAverageTrueRange(),
            trend.ParabolicSar(),
            trend.AverageDirectionalIndex(),
            trend.Aroon(),
            momentum.RelativeStrengthIndex(),
            momentum.MovingAverageConvergenceDivergence(),
            momentum.Stochastic(),
            momentum.CommodityChannelIndex(),
            momentum.WilliamsPercentRange(),
            momentum.RateOfChange(),
            momentum.MoneyFlowIndex(),
            volume.OnBalanceVolume(),
            volume.AccumulationDistribution(),
            volume.ChaikinOscillator(),
            patterns.CandlestickPatterns(),
        ]
        self._by_key = {}
        for indicator in self._indicators:
            self._by_key[indicator.key] = indicator

    def find(self, key: str) -> base.BaseIndicator:
        """Finds an indicator by its key.

        Args:
            key (str): The key, such as "rsi".

        Returns:
            base.BaseIndicator: The indicator.

        Raises:
            ValueError: No indicator has that key.
        """
        indicator = self._by_key.get(key)
        if indicator is None:
            raise ValueError(f'Unknown indicator: {key!r}')
        return indicator

    def describe(self) -> list[dict[str, Any]]:
        """Describes every indicator for the browser's picker.

        Returns:
            list[dict[str, Any]]: One description per indicator, in picker order.
        """
        descriptions = []
        for indicator in self._indicators:
            descriptions.append(indicator.describe())
        return descriptions
