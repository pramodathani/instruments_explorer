# instrument_routes.py

Filters arrive as repeated query parameters (`?shape=option&shape=future`), which FastAPI turns into lists. An instrument matches when it has any of a column's values, and different columns narrow each other.

The instrument route asks ubi for `details` and `additional_details` at the same time. When ubi fails, it still answers with the index's own record and the reason in `ubi_error`, so the page can show the name and identity while ubi is down. It answers 404 only when neither the index nor ubi knows the id.

The broker attributes are merged by taking, for each attribute, the first broker in ubi's order that publishes a value. Brokers usually agree on ISINs and names. The full per-broker table was left out as noise, and the broker list is on the contract card instead.

ubi failures are mapped as follows:

| ubi failure | Status |
|---|---|
| Unknown instrument | 404 |
| Bad request | 400 |
| Unreachable, stale data or no token | 503 |
| Anything else | 502 |
