# unified_broker_interface/

## Copied from sridhara

Most of these modules are copied from sridhara, with only the package names and a few wordings changed:

- `access_token_provider.py`
- `login_document.py`
- `redis_reader.py`
- `mongo_reader.py`
- `exceptions.py`
- `response_reader.py`
- `json_array_stream_parser.py`
- `configuration/unified_broker_interface_configuration.py`

Their tests are copied from sridhara too. Both projects talk to the same ubi under the same rules, so a fix found in one should be carried to the other.

## What was changed

- **The REST client.** `rest_client.py` is new and read-only. sridhara's client also places orders, reads the portfolio and streams ticks, none of which the explorer needs. Keeping those routes out of the file means the explorer cannot place an order even by mistake.
- **The error classes.** `exceptions.py` keeps sridhara's order-related classes (409, 422, 504), because the classes mirror ubi's status codes one to one. The explorer never triggers them.
- **The health check.** `health_checker.py` is new and much smaller than sridhara's. It calls ubi's unauthenticated greeting route and reads the stored login to say until when the token is valid. Its report has the same shape as the store checkers', so the status route treats ubi like any other service.

## Why the stored token and not connect

ubi issues one access token for all its clients, and every connect replaces it, which logs every other client out, such as sridhara and tradingmachine. The provider therefore reads the token ubi stored after its own login and connects only when there is none. `INSTRUMENTS_EXPLORER_UBI_MAY_CONNECT` can switch connecting off entirely.

## Why the master download works with a cold cache

On 2026-09-26 ubi's per-date catalogue cache in Redis was not warmed: `unified:catalogue:current_date` existed but none of its hashes did. The REST API still answered `master` from TimescaleDB, in 6.8 seconds for the whole catalogue, so nothing here reads the catalogue hashes directly.
