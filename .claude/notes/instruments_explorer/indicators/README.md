# indicators/

## One class per indicator, grouped by family

The user's rule is that similar cases each get their own self-contained class. The approved plan grouped them one module per family: moving averages, volatility, trend, momentum, volume and patterns. So each of the 22 indicators is its own class with its own `compute`, and the modules are the families.

`BaseIndicator` holds only what is genuinely identical: the description sent to the browser, checking and defaulting parameters, the legend title, and the warm-up estimate. There is no dynamic dispatch on TA-Lib function names. Each class calls its TA-Lib function directly, so reading one class tells you everything about that indicator. The pattern finder maps pattern keys to TA-Lib functions in an explicit dictionary for the same reason.

## Request format

A chart asks for each indicator as `key:param:param`, such as `bbands:20:2`. Parameters left out take their defaults. The format was chosen because it fits in a URL, so the browser keeps the chosen indicators in the page address and a chart can be shared as a link. It is also readable, and one query parameter per indicator makes the order obvious.

## Errors do not break the chart

A bad request (unknown key, out-of-range parameter, a volume indicator on an index) becomes a message in `errors`, and the other indicators are still computed. At most 12 indicators are computed per chart, which keeps the chart legible and the request cheap.

## Warm-up

An indicator has no value until it has seen enough candles; SMA 50 needs 50. Computing only over the visible range would leave the first stretch of every line blank.

`warm_up_candles` adds up an indicator's whole-number parameters. That covers stacked look-backs, such as MACD's slow average followed by its signal average (12 + 26 + 9 = 47). The chart route turns the longest warm-up into extra calendar days (1.6 calendar days per trading day, plus 10), reads that much more history from ubi, computes, then trims.

Exponential averages and RSI keep converging for a while after their first value, so the estimate errs on the generous side. On 2026-09-26 all 22 indicators over RELIANCE's 1,661 daily candles took 51 ms together.

## Volume

MFI, OBV, A/D and Chaikin need volume. Indices report zero volume, so those four are refused with a clear message, and the picker greys them out. Missing volumes in otherwise valid series are treated as zero, because TA-Lib would otherwise spread NaN through the whole running total.

## Patterns

Nine TA-Lib candlestick patterns become markers rather than lines. On RELIANCE's daily history they fired 529 times in 1,661 candles, mostly doji and harami. The chart therefore hides those two by default, and each pattern can be switched on or off from the legend.
