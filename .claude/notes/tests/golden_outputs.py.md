# tests/golden_outputs.py

## Why the golden files exist

On 2026-09-26 the project began moving its UBI access and its indicator computations onto the sibling library tradingmachine. The golden files record, from the code as it stood before that move, every number the browser and the screener see:

- the indicator calculator's answer for every indicator key at its defaults, and for a set of non-default parameters (`NON_DEFAULT_REQUESTS`);
- the screener's `StockMetrics` figures;
- the chart route's full answer (`ChartRoutes._build_answer`), which includes the warm-up history being trimmed from candles, lines and markers.

`tests/test_golden_outputs.py` recomputes these outputs on every run and compares them with the files as text, so a refactor that changes any value, even in the last decimal place, fails the test. The comparison is textual rather than numeric because NaN never equals itself, while the text `NaN` does.

## Fixtures

`tests/fixtures/prices/` holds UBI prices documents, unchanged from the REST answer:

| Fixture | Source | Why it is included |
|---|---|---|
| `reliance_day` | RELIANCE, NSE, 1,100 days, adjusted | An ordinary share with volume |
| `reliance_day_unadjusted` | RELIANCE, 400 days, unadjusted | The unadjusted price basis |
| `nifty_day` | NIFTY index, 1,100 days | Zero volume, so volume indicators report an error |
| `gold_future_day` | MCX gold future, 400 days | A commodity future with open interest |
| `synthetic_missing_volume` | `fakes.PricesMaker`, 300 candles | Every seventh volume is null, which the volume indicators must treat as zero |
| `synthetic_gaps` | `fakes.PricesMaker`, 300 candles | Missing closes (skipped candles), highs and opens (NaN inputs) |
| `synthetic_short` | `fakes.PricesMaker`, 10 candles | Shorter than most look-back periods, and than the screener's minimum |
| `synthetic_flat` | `fakes.PricesMaker`, 120 candles | Constant prices and no volume, which make some indicators divide by zero |
| `synthetic_5minute` | Written by hand, 1,500 five-minute candles | Intraday times; UBI held no intraday candles for RELIANCE on 2026-09-26 |

The real documents were read with the project's own client with `may_connect=False`, so recording them could never replace UBI's token. Each fixture's `to` date fixes where the chart trims, so the outputs do not depend on today's date.

## File format

The golden files are compact JSON with sorted keys, gzip-compressed with a zero timestamp so the bytes are the same every time they are written. As indented JSON they came to 22 MB; compressed they are about 2.5 MB.

## Regenerating

Regenerate only when a change to the numbers is intended, and say so in the commit message:

```bash
PYTHONPATH=. .venv/bin/python -c "
from tests import golden_outputs
outputs = golden_outputs.GoldenOutputs()
for name in golden_outputs.FIXTURE_NAMES:
    outputs.write_golden(name)
"
```
