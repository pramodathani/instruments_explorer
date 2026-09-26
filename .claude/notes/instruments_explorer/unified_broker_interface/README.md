# unified_broker_interface/

## Since 2026-09-26: UBI is reached through tradingmachine

All UBI access goes through the sibling library tradingmachine (`~/Projects/tradingmachine`), installed in editable mode from `requirements.txt`. The user chose this on 2026-09-26 so that one library is the Python way into UBI, and asked that every missing piece be built into tradingmachine rather than kept here. This package now holds only the adapters between tradingmachine's blocking classes and this project's asyncio code:

```
tradingmachine_components.py  TradingmachineComponents: builds tradingmachine's client, token source, catalogue and live quote reader from UBI's .env
catalogue_gateway.py          CatalogueGateway: the seven async reads the rest of the project uses, each run in a worker thread
live_quote_gateway.py         LiveQuoteGateway: many live quotes at once from UBI's Redis, in a worker thread
health_checker.py             HealthChecker: UBI's row on the status page
```

What each piece of the old code became:

| Removed from this package | Now in tradingmachine |
|---|---|
| `rest_client.py` (async httpx client) | `ubi_client.client.UnifiedBrokerInterface`, `ubi_client.instrument_catalogue.InstrumentCatalogue`, behind `CatalogueGateway` |
| `json_array_stream_parser.py` and the streamed master | `ubi_client.json_array_stream_parser`, `ubi_client.instrument_master_stream.InstrumentMasterStream` |
| `access_token_provider.py` | `ubi_stores.stored_login_token_source.StoredLoginTokenSource` |
| `login_document.py` | `ubi_stores.stored_login.StoredLogin` |
| `redis_reader.py`, `mongo_reader.py` | `ubi_stores.stored_login_reader.StoredLoginReader`, `ubi_stores.live_quote_reader.LiveQuoteReader` |
| `exceptions.py`, `response_reader.py` | `ubi_client.exceptions`, with the same class names and status mapping |

Their tests moved to tradingmachine's `tests/` with them. `configuration/unified_broker_interface_configuration.py` stays here, because it reads UBI's own `.env`, so that no copy of UBI's passwords is kept in this project, and hands the values to tradingmachine in code.

`tests/test_read_only_sources.py` guards the result: nothing outside `storage/` imports `redis` or `pymongo`, nothing imports tradingmachine's orders, accounts or instrument classes (which can place orders), this package never calls a connect, disconnect or writing route, and tradingmachine's store readers offer only reads.

The move was checked by recording the chart, indicator and screener outputs beforehand (`tests/fixtures/golden/`, see `.claude/notes/tests/golden_outputs.py.md`) and 33 live API responses on port 8101 before and after; see the commit "Reach UBI through tradingmachine".

## Why the stored token and not connect

UBI issues one access token for all its clients. Until UBI's change of 2026-09, every connect replaced it and logged every other client out, such as sridhara and tradingmachine; since then, a connect after the most recent 07:00 hands back the token already in force, but the first connect after 07:00 still replaces it. The token source therefore reads the token UBI stored after its own login and connects only when there is none. `INSTRUMENTS_EXPLORER_UBI_MAY_CONNECT` can switch connecting off entirely, and `INSTRUMENTS_EXPLORER_UBI_CONNECT_COOLDOWN_SECONDS` spaces connect attempts.

## Why many quotes come from Redis

UBI's quote routes answer for one instrument per request, and UBI has no bulk or streaming quote route. The live relay, the option chain and the universe map need hundreds to hundreds of thousands of quotes at a time, so tradingmachine's `LiveQuoteReader` reads UBI's `unified:quotes:live` hash with `HMGET`, as UBI's own order engine does.

## History: copied from sridhara, until 2026-09-26

The old modules were copied from sridhara with only package names and a few wordings changed, apart from the read-only REST client and the smaller health check, which were written here. sridhara still has its own copies; this project no longer needs to keep in step with them.

## Why the master download works with a cold cache

On 2026-09-26 ubi's per-date catalogue cache in Redis was not warmed: `unified:catalogue:current_date` existed but none of its hashes did. The REST API still answered `master` from TimescaleDB, in 6.8 seconds for the whole catalogue (4.9 seconds through tradingmachine later that day), so nothing here reads the catalogue hashes directly.
