# chart_routes.py

## Intervals and limits

The intervals and limits mirror ubi's prices route: a `day` range may be up to 36,500 days, an intraday range at most 366. They are checked here, before calling ubi, so a bad request fails fast with a readable message.

## Warm-up and trimming

`_first_time` finds the chart's first day from ubi's own `to` date minus the requested days, at midnight India time. That matches how ubi counts its `days` window, with both ends inclusive. Candles and indicator points before that moment are dropped after computing.

## Times

ubi sends candle times as ISO strings in UTC (a daily candle starts at `18:30+00:00`, which is midnight in India). `CandleSeries` turns them into epoch milliseconds, which is what Highcharts wants. The browser formats them in India time through Highcharts' `time.timezone`.

## Computing in a thread

TA-Lib is fast, but building the answer also walks every candle in Python, which can be tens of thousands of intraday rows. The work runs in a worker thread so one large chart never stalls the live quote WebSocket.
