# indicators/

## One class per indicator, grouped by family

The user's rule is that similar cases each get their own self-contained class. The approved plan grouped them one module per family: moving averages, volatility, trend, momentum, volume and patterns. So each of the 22 indicators is its own class with its own `compute`, and the modules are the families.

`BaseIndicator` holds only what is genuinely identical: the description sent to the browser, checking and defaulting parameters, the legend title, the warm-up estimate, and `column`, which reads one computed column out of tradingmachine's answer. There is no dynamic dispatch on method names. Each class calls its tradingmachine analysis method directly, so reading one class tells you everything about that indicator. The pattern finder calls each of its nine pattern methods by name in its `compute`, for the same reason.

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

## Computed by tradingmachine since 2026-09-26

The indicators used to call TA-Lib directly. On 2026-09-26, when UBI access moved onto the sibling library tradingmachine, the user chose to compute them with tradingmachine's analysis methods as well, so the project keeps no TA-Lib code of its own.

`CandleAnalysisFactory.create` turns a `CandleSeries` into tradingmachine's `CandleFrameAnalysis`: a DataFrame of `open`, `high`, `low`, `close`, `volume` and `oi`, one row per candle, with missing volume replaced by zero, as the volume indicators always did. `IndicatorCalculator.compute` builds it once per chart and hands it to every requested indicator, so a chart of twelve indicators is still one read of UBI's candles, with the warm-up history included. Each class's `compute(analysis, parameters)` calls one tradingmachine method and reads the column it adds:

| Key | tradingmachine method | Column read |
|---|---|---|
| sma, ema, wma, dema | `simple_`, `exponential_`, `weighted_`, `double_exponential_moving_average` | `sma_<p>`, `ema_<p>`, `wma_<p>`, `dema_<p>` |
| tema | `mulloy_triple_exponential_moving_average` | `tema_<p>` |
| bbands | `bollinger_bands(p, d, d)` | `bb_upper_<p>`, `bb_middle_<p>`, `bb_lower_<p>` |
| atr, natr | `average_true_range`, `normalized_average_true_range` | `atr_<p>`, `natr<p>` |
| sar | `parabolic_sar` | `psar` |
| adx | `average_directional_movement_index`, `plus_directional_indicator`, `minus_directional_indicator` | `adx_<p>`, `plus_di_<p>`, `minus_di_<p>` |
| aroon | `aroon` | `aroon_up_<p>`, `aroon_down_<p>` |
| rsi, cci, willr, roc, mfi | `relative_strength_index`, `commodity_channel_index`, `williams_percent_r`, `rate_of_change`, `money_flow_index` | `rsi_<p>` and so on |
| macd | `moving_average_convergence_divergence` | `macd_<f>_<s>_<g>`, `_signal`, `_hist` |
| stoch | `stochastic_oscillator(fast_k, slow_k, 0, slow_d, 0)` | `slowk_<k>`, `slowd_<d>` |
| obv, ad, adosc | `on_balance_volume`, `chaikin_accumulation_distribution_line`, `chaikin_accumulation_distribution_oscillator` | `obv`, `chaikin_ad`, `chaikin_adosc<f>_<s>` |
| patterns | `candle_doji` and the eight others | `candle_<name>` |

Two of tradingmachine's names are traps. Its `triple_exponential_moving_average` is Tillson's T3, not the TEMA this chart has always shown, so the `tema` key uses `mulloy_triple_exponential_moving_average`, which tradingmachine gained for this move. And its NATR column is `natr14`, without the underscore the others have.

Whole-number parameters are passed through `int(...)` so a column name never reads `sma_20.0`.

**Checked to be identical.** Before the old code was removed, every indicator was run the old way and the new way over nine prices fixtures (four real UBI series and five synthetic ones with missing volume, gaps, flat prices, a short series and five-minute candles), at default and non-default parameters: all 585 output arrays were bit-for-bit equal, and so were the screener's figures. `tests/test_golden_outputs.py` keeps checking the rounded answers the browser sees against files recorded before the move.

**Cost.** All 22 indicators over RELIANCE's 743 daily candles took 22 ms the old way and 29 ms the new way on 2026-09-26, the difference being the DataFrame copies tradingmachine makes per method. That is small beside the time to read the candles from UBI.
