# instruments_explorer/unified_broker_interface/live_quote_gateway.py

`LiveQuoteGateway.read` runs tradingmachine's `LiveQuoteReader.read` in a worker thread. It replaced the async `RedisReader.hash_get_many_json` on 2026-09-26. Its callers are the live quote relay (`market/live_quote_reader.py`, twice a second while a browser watches instruments) and the snapshot reader behind the option chain and the universe map (`market/quote_snapshot_reader.py`).

A Redis failure arrives as tradingmachine's `UnreachableError` rather than `redis.RedisError`, so no module outside tradingmachine needs to import `redis` any more.

Thread cost: one `to_thread` hop is tens of microseconds, against a Redis round trip of a few hundred. The universe map with options reads about 236,000 quotes; the snapshot reader passes them to tradingmachine in one call, which batches them 500 to an `HMGET`, so that is one thread hop rather than 473.
