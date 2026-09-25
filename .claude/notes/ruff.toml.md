# ruff.toml

This file is copied from sridhara, which is the stricter of the two sibling projects.

- `force-single-line` with module imports enforces the rule that each import names one module on its own line.
- Single quotes and an 80-column limit follow the Google style guide. The formatter does not split long strings, which keeps the rule that a sentence is never split across lines.
- `FLY002`, `TRY004` and `UP040` are ignored for the same reasons as in sridhara: they push toward f-string joins, `TypeError` for value checks, and the `type` statement, none of which suit the code style here.
