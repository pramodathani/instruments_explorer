# instruments/

## Why not sridhara's index

sridhara's index is built to reproduce Kite's search: Kite-style names, weekly expiry detection, and a ranking tuned for traders typing into a watchlist. The explorer needs something else, namely filter counts per exchange, asset class, kind, segment, option type and expiry month over the whole catalogue. So the builder and index are new. Only `search_query_parser.py` is copied from sridhara, because turning typed words into a safe FTS5 prefix expression is exactly the same job.

## What is stored

Expired contracts are left out; everything else is kept, including ubi's uncategorised segments. On 2026-09-26 that was 236,431 of the 539,207 instruments in ubi's catalogue, in a 97 MB file built in about 7 seconds.

Each instrument is stored once in the `instruments` table and once in the contentless FTS5 table, sharing a row number. The builder assigns row numbers itself instead of relying on `INSERT OR IGNORE`, because a skipped duplicate would otherwise leave an FTS row pointing at nothing. Duplicates are found with a set of the ids already seen.

## Asset classes

`asset_classifier.py` maps ubi's bare segment names onto six asset classes by keyword, checking fixed income before currency, commodity and equity. The order matters because `fixed_income_index_futures` would otherwise match nothing and `equity` must not catch "fixed income". Index segments are flagged separately, so "NIFTY" the index ranks above stocks named like it.

## Filter counts

Each facet column is counted with every filter applied except its own. This is the usual faceted-search rule: with "Futures" chosen, the Kind group still shows how many options and cash instruments there would be. Without it, choosing one value would make every other value in its group vanish.

The counts are cached per (text, filters, strike range), up to 256 entries. The unfiltered counts over the whole catalogue take about 120 ms, and people ask for them constantly: every page load and every cleared filter.

## Ranking

Relevance order puts names equal to the first word first, then names starting with it, then other matches. Within those it orders cash before futures before options, indices first, then NSE, BSE, MCX and NCDEX, shorter names, expiry and strike. MCX commodities therefore come after NSE's commodity contracts of the same name. That can be tuned later if it annoys.

## Lot size and company names

The master carries only the nine identity fields. ubi has lot sizes and company names only per instrument (`details`, `additional_details`) or in its order-path Redis hashes, so neither is in the index yet. Company names will join the search in phase 5, from the knowledge pipeline.
