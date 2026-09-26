# market/

## Reading the hash, not the stream

The first plan was to follow ubi's quote stream, `unified:quotes:stream`. sridhara found that the stream now carries the whole market's ticks, because the Zerodha feed subscribes to its entire instrument list, while a browser watches a handful. Reading `unified:quotes:live` with HMGET for only the watched instruments makes the cost depend on what is on screen, not on how busy the market is. `LiveQuoteReader` does that twice a second and delivers a quote only when its `received_at` has changed.

## Batching per connection

`live_connection.py` is sridhara's `ClientConnection`, renamed. It keeps only the newest quote per instrument and sends them together every quarter second, so a busy instrument ticking many times a second costs the browser one update per batch, and a slow browser never builds up a backlog. Its event queue is unused for now; fetch-job progress will use it in phase 5.

## The hub

`LiveQuoteHub` is new and much smaller than sridhara's `LiveHub`, which also serves a trading engine, polls ubi's quote route for instruments without a live feed, and knows market hours. A new subscriber gets the latest quote the hub already holds straight away, because the reader delivers only changed quotes and a quiet instrument might otherwise show nothing until it trades. The latest quotes of instruments nobody watches are dropped.

## The first quote

The instrument page asks ubi's REST quote route once, then relies on the live feed. That route answers from ubi's cache and falls back to a live broker call when the cache is older than five minutes during a session, so it is not polled.
