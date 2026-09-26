# charts/

## Highcharts Stock

The user chose Highcharts and Highcharts Stock; they are free for personal, non-commercial use. The chart module is loaded lazily with the instrument page's `ChartPanel`, so the 397 kB chart bundle does not delay Explore or Overview.

## Two pitfalls met on 2026-09-26

- **The React wrapper's import.** `highcharts-react-official` 3.2.3 ships a UMD/CommonJS bundle. Under Vite 8 (rolldown), its default import resolved to the module object, and React failed with minified error 130 ("element type is invalid: got object"). The named import `{ HighchartsReact }` is the component.
- **Shared ids.** Highcharts keeps series and axes in one id namespace (`chart.get(id)`). A candlestick series and its axis both called `price` made the candles and volume silently disappear while the indicator lines drew. Axes are therefore named with an `-axis` suffix.

## Layout

The price pane takes what is left after the volume pane (14%) and one pane per panel indicator (17% each), with 2% gaps. The chart's pixel height grows with the pane count, so indicator panes never get squeezed. Reference levels (RSI 30/70 and the like) come from the server as `reference_lines` and are drawn as dashed plot lines.

## Theme

`HighchartsTheme` reads the page's CSS tokens and calls `Highcharts.setOptions` before each build. The chart component is keyed by the theme, so switching light and dark rebuilds it with the new colours. The chart card has a solid background instead of the usual translucent card, because the animated backdrop showing through price lines was distracting.

## Today's candle

ubi's price loader runs once a day and the stored history can stop days before today. `LiveCandleMerger` appends, or replaces, a candle for today built from the live quote's open, high, low, last price and volume, but only on daily charts. The footnote says when that has happened.

## State in the address

Interval, period, adjustment, view and indicators are query parameters. An empty `indicator=` means "no indicators", which is different from no parameter at all; that case gets the default SMA 20 and RSI 14.
