# requirements.txt

## tradingmachine, since 2026-09-26

`-e ../tradingmachine` installs the sibling library tradingmachine (`~/Projects/tradingmachine`) in editable mode, so the project always runs the library's current code without reinstalling. From 2026-09-26 all UBI access goes through it: the REST client, the stored-token source, the live quote reader and the TA-Lib analysis methods the charts and screener use.

The path is relative, and pip resolves it against the directory it is run from, so install from the project root as the Commands table in `CLAUDE.md` says. Because the install is editable, a change in tradingmachine reaches the running service at its next restart (`systemctl --user restart instruments-explorer`); pinning a tag or commit instead would make upgrades deliberate, which may be worth doing once the library settles.

tradingmachine brings in `backtesting` and, through it, `bokeh`, because the analysis classes include backtesting and are imported together. instruments_explorer does not use either.

`pandas` is pinned because the indicator code now builds pandas DataFrames for tradingmachine; it had been installed only as a dependency of other packages. `TA-Lib`, `redis` and `pymongo` stay pinned at the versions this project was tested with, although tradingmachine also requires them, so the environment is reproducible.

tradingmachine's histogram methods draw with matplotlib, which the library does not declare and this project does not install; they are never called here.
