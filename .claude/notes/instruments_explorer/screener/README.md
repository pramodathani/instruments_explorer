# screener/

## Where sectors come from

A heatmap by sector needs a sector for every stock. Asking Yahoo about 2,500 stocks one at a time would be slow and heavy on Yahoo. NSE publishes the Nifty Total Market constituents, about 755 stocks and roughly 90% of the market's value, with an "Industry" column, in one CSV that robots.txt allows. Those industries are the heatmap's sectors, and the Nifty Total Market is the default universe.

For stocks outside that list, `CompanyRepository.sector` falls back to Screener.in's top-level classification and then Yahoo's sector, where a company has been fetched; otherwise the sector is "Unclassified".

## Figures are stored, screens are not

The figures job reads each stock's candles once a day, and every screen then reads MongoDB only. Screens are instant and never put load on ubi or the brokers, and changing a condition's numbers costs nothing. The figures are as of the last candle ubi has stored, which the rows record as `last_candle_date`.

## Runtime

On 2026-09-26 a run of the 750-stock universe took under five seconds, with 744 stocks computed and 6 skipped for having fewer than 30 candles. That speed comes from ubi's Redis candle cache. With a cold cache it would be slower, but still minutes rather than hours at four requests at a time.

## Crossovers

`StockMetrics._days_since_cross` looks back at most 20 candles for the latest crossing of two lines and reports how many candles ago it happened. The golden and death cross conditions (50 over 200-day) and the MACD turn condition test that number against their "within" parameter.

## Conditions with fixed periods

The figures hold returns for 1, 5, 21, 63 and 252 trading days and averages for 20, 50 and 200 days only, so the return and average conditions refuse other periods with a clear message instead of silently matching nothing.

## Odd values seen in real data

HG Infra showed a volume 221 times its 20-day average, most likely one large block deal, and PolicyBazaar a 36% one-day fall. Both come straight from ubi's stored candles; the screener does not second-guess them.
