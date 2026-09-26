# instruments_explorer/unified_broker_interface/catalogue_gateway.py

`CatalogueGateway` was added on 2026-09-26, when all UBI access moved onto the sibling library tradingmachine. It has exactly the seven async methods, answers and errors of the `UnifiedBrokerInterfaceClient` it replaces (`greeting`, `instrument_segments`, `download_master`, `instrument_details`, `additional_details`, `quote`, `prices`), so the routes, the index builder and maintainer, the screener job, the company resolver and the chat assistant did not have to change beyond their exception import, and neither did `tests/fakes.py::FakeCatalogueClient`, which stands in for it.

## Worker threads

tradingmachine sends requests with the blocking `requests` library, so every call runs in `asyncio.to_thread`. The default thread pool has `min(32, cpu_count + 4)` workers, which is plenty for one user's browser: the screener reads four stocks at a time, and a chart, a quote and the index check are one request each. tradingmachine's client keeps 16 pooled connections (`TradingmachineComponents.CONNECTION_POOL_SIZE`), so threads never wait for a connection.

A thread cannot be cancelled. When a request's task is cancelled, as at shutdown, the thread finishes its HTTP call (at most the 30-second timeout) and its answer is thrown away. That is also why the master download closes its stream in `finally`: closing releases the connection even if the loop stops between batches.

## The master download

`download_master` opens tradingmachine's `InstrumentMasterStream` in a thread, then alternates: one `next_batch` in a thread, then `await handle_batch(batch)` in the event loop, where the index builder hands the batch to SQLite in its own thread. Only one batch of 5,000 identities is in memory at a time, as before. A master that stops early now raises tradingmachine's `IncompleteResponseError`, a `UnifiedBrokerInterfaceError`, where the old client raised `ValueError`; the maintainer catches both.

## What changed for callers

Nothing in the answers: `prices` returns tradingmachine's `PricesDocument.document`, the very dict UBI sent. The exception classes now come from `tradingmachine.ubi_client.exceptions`, which has the same names and the same mapping from status codes, plus `LossLockoutError` for 403, which no read route returns. Three fallback messages are worded differently, such as "UBI returned HTTP 500" for the old "UBI answered HTTP 500", and "Could not reach UBI at <url>: ..." when no answer arrived; UBI's own `error` text, which is what nearly every failure carries, passes through unchanged.
