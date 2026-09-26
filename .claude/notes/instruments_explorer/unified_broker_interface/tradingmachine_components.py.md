# instruments_explorer/unified_broker_interface/tradingmachine_components.py

`TradingmachineComponents` builds, in one place, the tradingmachine objects the project reaches UBI through, and closes them together at shutdown. It was added on 2026-09-26.

## Settings come from UBI's .env, not tradingmachine's

`configuration/unified_broker_interface_configuration.py` still reads UBI's own `.env` for the addresses and passwords of UBI's REST API (8080), Redis (1002) and MongoDB (1003), so no copy of UBI's secrets is kept in this project. The values are handed to tradingmachine as `RedisSettings` and `MongoSettings` objects and a `base_url`, together with a token source. With both a base url and a token source given, tradingmachine's client never builds its own `Configuration`, which would search for tradingmachine's `.env` and load its `TRADINGMACHINE_*` variables (tradingmachine's own databases on ports 2002 and 2003) into this process's environment. `tests/test_tradingmachine_gateways.py` checks that no such variable appears.

## The token rule is kept

The token source is `StoredLoginTokenSource`, tradingmachine's port of this project's old `AccessTokenProvider`: it uses the token UBI has stored in its Redis or MongoDB, adopts a newer stored token after a refusal, and connects only when there is no usable token, only if `INSTRUMENTS_EXPLORER_UBI_MAY_CONNECT` allows it, and at most once per `INSTRUMENTS_EXPLORER_UBI_CONNECT_COOLDOWN_SECONDS`. That keeps the project's rule of never connecting while a stored token is usable.

## Sizes

The client keeps 16 pooled connections, more than the thread pool will run at once for this project's traffic (four screener reads, a chart, a quote, the index check), so no request waits for a connection. Every timeout is `INSTRUMENTS_EXPLORER_UBI_REQUEST_TIMEOUT_SECONDS` (30 by default), as before.

Nothing connects when the components are built: `requests`, `redis` and `pymongo` all connect on first use, so the server starts even while UBI is down.
