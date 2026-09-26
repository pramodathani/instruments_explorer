# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

instruments_explorer is a password-protected web application for exploring the instruments that the sibling project unified_broker_interface (ubi, `~/Projects/unified_broker_interface`) knows about. It shows instruments, quotes, candles and TA-Lib indicators taken from ubi, together with company data that it downloads from the internet and stores in its own MongoDB and ChromaDB. It also has a Claude chat assistant that can drive the site. The stack and conventions are copied from the sibling projects `sridhara` and `system_monitor`.

The full, approved build plan is in `~/.claude/plans/there-is-a-sibling-starry-lagoon.md`. The work is split into eight phases, and phases 1 to 5 are done:

| Phase | Contents |
|---|---|
| 1 | Scaffold: application, login, status route, containers, frontend shell with the three.js backdrop, chat panel shell |
| 2 | ubi access token and REST client, SQLite FTS5 instrument index, Explore page, quote header, live quote relay |
| 3 | Candles, TA-Lib indicators, Highcharts Stock chart, 3D candle view |
| 4 | Option chain, implied volatility, 3D volatility surface |
| 5 | Knowledge pipeline: fetchers, MongoDB, ChromaDB, Knowledge page, company tab |
| 6 | Screener and sector heatmap |
| 7 | 3D universe map and polish |
| 8 | Claude chat assistant |

## Commands

| Task | Command |
|---|---|
| Create the environment | `python3.14 -m venv .venv && .venv/bin/pip install -r requirements.txt` |
| Start MongoDB and ChromaDB | `docker compose up -d --wait` |
| Run all tests | `.venv/bin/pytest` |
| Run one test | `.venv/bin/pytest tests/test_routes.py::TestRoutes::test_login_and_logout` |
| Lint and format check | `.venv/bin/ruff check . && .venv/bin/ruff format --check .` |
| Build the frontend | `source ~/.nvm/nvm.sh && cd frontend && npm install && npm run build` |
| Typecheck the frontend only | `source ~/.nvm/nvm.sh && cd frontend && npm run typecheck` |
| Frontend dev server (port 5175, forwards `/api` to 8100) | `source ~/.nvm/nvm.sh && cd frontend && npm run dev` |
| Set the login password | `bin/set-password`, then paste its two lines into `.env` |
| Run the server (port 8100) | `bin/instruments-explorer` |
| Run as a service | `systemctl --user link ~/Projects/instruments_explorer/services/instruments-explorer.service`, then `systemctl --user enable --now instruments-explorer` |

`npm run build` runs `tsc --noEmit` before `vite build`, so it is also the frontend typecheck. The server serves `frontend/dist`, so rebuild the frontend before checking a change in the browser on port 8100.

## Architecture

The browser talks only to this project's FastAPI server. The server reads ubi and owns two stores of its own.

- **Backend** (`instruments_explorer/`). `Application` (`application.py`) has three steps:
  - `build()` creates the real components from `Settings`.
  - `create_web_application()` assembles the FastAPI app from ready components. Tests call it directly with stand-ins from `tests/fakes.py`.
  - `_lifespan` closes the connections on shutdown.
- **Routes.** Each route group is a class in `routes/` whose `router` is included in order. `FrontendRoutes` is a catch-all that serves the built single-page app, so it must always be included last.
- **Security.** `security/` holds the argon2 password check with lockout, the signed session cookie, and the `X-Requested-With: instruments-explorer` header that every POST must carry.
- **Settings.** All settings come from `INSTRUMENTS_EXPLORER_*` variables through `configuration/settings.py`. `.env.example` lists them all.
- **Own stores.** `docker-compose.yml` runs MongoDB (host port 3003) and ChromaDB (host port 3004) on their own Docker network, `instruments_explorer_network`, bound to 127.0.0.1. `storage/` holds one connection class per store; each has a `check()` used by `/api/status`.
- **ubi access** (`unified_broker_interface/`). ubi is reached only through its published host ports: the REST API at 127.0.0.1:8080, Redis at 1002 and MongoDB at 1003. Their addresses and credentials are read from ubi's own `.env` by `configuration/unified_broker_interface_configuration.py`, so no copy of ubi's passwords is kept here.
  - `AccessTokenProvider` uses the token ubi has stored in Redis (or MongoDB) and connects only when none is usable. `RedisReader` and `MongoReader` expose read commands only.
  - `rest_client.py` is read-only: greeting, segments, the streamed master, details, additional details and quote.
  - These modules, their error classes and their tests are copied from sridhara; keep them in step with sridhara when fixing either.
- **Instrument index** (`instruments/`).
  - `InstrumentIndexBuilder` streams ubi's `master` (about 540,000 instruments, 127 MB, 7 seconds) into `data/instruments/instruments-<mapping date>.sqlite`. It keeps the roughly 236,000 that have not expired, with an asset class, a readable name and full-text search words for each.
  - `InstrumentIndex.search()` returns one page of results, the total and a count for every filter value. Each filter's counts are taken with every other filter applied but not its own.
  - `InstrumentIndexMaintainer` checks ubi's mapping date every ten minutes and swaps in a new index when it changes.
  - Filter column names come only from `FACET_COLUMNS`, and every value is a bound parameter.
  - ubi has no bulk route for lot sizes or company names, so they are not filterable. Lot size comes from ubi's `details` on the instrument page, and company names join the index in phase 5.
- **Charts and indicators** (`indicators/`, `routes/chart_routes.py`, `market/candle_series.py`).
  - `GET /api/instruments/{id}/chart?interval=&days=&adjusted=&indicator=rsi:14&indicator=macd:12:26:9` reads candles from ubi's `prices` route and computes TA-Lib indicators on the server.
  - An indicator request is its key followed by colon-separated parameters in the indicator's order; parameters left out take their defaults.
  - The route reads extra warm-up history so every indicator has values from the chart's first candle, then trims candles and lines back to the requested range.
  - Each indicator is its own class in its family's module (`moving_averages.py`, `volatility.py`, `trend.py`, `momentum.py`, `volume.py`, `patterns.py`), over a shallow `BaseIndicator`. `IndicatorCatalogue` lists them explicitly; add a new indicator there.
  - ubi stores only daily candles for most instruments; intraday history exists only where someone loaded it by hand.
- **Derivatives** (`derivatives/`, `routes/derivative_routes.py`, `market/quote_snapshot_reader.py`).
  - `/api/derivatives/underlyings`, `/expiries`, `/chain` and `/surface` take `exchange` and `underlying`, plus `expiry` for the chain.
  - `OptionChainBuilder` takes an underlying's contracts from the index and reads all their quotes at once from ubi's `unified:quotes:live` hash through `QuoteSnapshotReader`, never one REST call per contract.
  - `BlackModel` and `ImpliedVolatilitySolver` (bisection) give implied volatility and the Greeks. The forward is the same-expiry future's price, else the spot carried forward at `INSTRUMENTS_EXPLORER_RISK_FREE_RATE`, else the nearest future. `ExpiryClock` counts to 15:30 India time on the expiry date.
  - Implied volatility uses the mid of a tight bid and offer, or the last price only when the contract traded today. An untraded contract's last price is an old close and gives false volatility.
  - The surface's strikes come from the nearest expiry within 8% of its forward; gaps are interpolated, never extrapolated, and lone spikes are dropped.
- **Company knowledge** (`knowledge/`, `storage/*_repository.py`, `routes/knowledge_routes.py`).
  - Each source is its own fetcher class in `knowledge/fetchers/`: NSE announcements, Yahoo Finance (through yfinance), Screener.in, Wikipedia, seven RSS news feeds, Bing News RSS and Google Programmable Search. Wikipedia stays off until `INSTRUMENTS_EXPLORER_KNOWLEDGE_CONTACT` is set, because its robot policy asks for contact details; Google search stays off until its API key and engine id are set.
  - Every fetcher except yfinance goes through `PoliteHttpClient`, which checks robots.txt (cached a day) and waits `INSTRUMENTS_EXPLORER_KNOWLEDGE_HOST_INTERVAL_SECONDS` between requests to one site. Google News RSS is blocked by its robots.txt, and NSE's per-company quote API sits behind Akamai bot detection, so neither is used.
  - `ListingImporter` loads NSE's `EQUITY_L.csv` (about 2,585 companies with names and ISINs) into the `companies` collection on first start and on demand. The instrument index then includes company names, so "infosys" finds INFY.
  - `CompanyResolver` maps an instrument to its company: a derivative to its underlying's company, keyed by ISIN; indices, commodities, currencies and bonds are refused.
  - `FetchJobRunner` runs one job at a time in the background, one step per source, so a failing site never stops the others. It saves each change to `fetch_jobs` and broadcasts it on `/api/live` as a `fetch_job` event. `KnowledgeScheduler` repeats the news sources for fetched companies every `INSTRUMENTS_EXPLORER_KNOWLEDGE_REFRESH_HOURS`.
  - `KnowledgeService` merges profile fields into `companies` with `$set` (sources never overwrite each other), stores documents in `documents`, and embeds them in the ChromaDB collection `company_documents` with the local all-MiniLM-L6-v2 model (downloaded once to `~/.cache/chroma`).
  - The index file carries a `schema_version`; a file built by older code is rebuilt automatically instead of failing.
- **Live quotes** (`market/`). `LiveQuoteReader` reads `unified:quotes:live` in Redis twice a second, but only for the instruments some browser watches. `LiveQuoteHub` hands each changed quote to the watching `LiveConnection`s, which merge quotes per instrument and send them in batches every quarter second over the `/api/live` WebSocket. That WebSocket checks the Origin header and the session before accepting.
- **Frontend** (`frontend/`). React 19, TypeScript 7, Vite 8 and react-router 8, with three.js and Highcharts / Highcharts Stock.
  - The Explore page (`explore/`) keeps its whole search in the page address through `SearchState`, so the back button, reloading and shared links keep the search.
  - The instrument page (`instrument/`) loads a quote over REST once, then follows it through `useLiveQuote`, which retains the instrument on the shared `LiveSocket` (`live/`).
  - The derivatives page (`derivatives/`) keeps the underlying, expiry, tab and strike range in the page address and refreshes the chain every five seconds while the tab is visible. Its 3D surface is `three/surfaceScene.ts`.
  - The knowledge page (`knowledge/`) and each instrument page's `CompanyPanel` follow fetch jobs live through `LiveSocket.onFetchJob`.
  - The chart (`charts/`) is Highcharts Stock, loaded lazily with the instrument page's `ChartPanel`. Its interval, period, adjustment, 2D/3D view and indicators live in the page address. `ChartOptionsBuilder` lays out the price pane, the volume pane and one pane per panel indicator. `LiveCandleMerger` adds today's candle from the live quote when ubi's stored history stops before today.
  - Import the React wrapper as `import { HighchartsReact } from 'highcharts-react-official'`. The default import resolves to the CommonJS module object under Vite and crashes React with error 130.
  - Highcharts series and axes share one id namespace, so axes are named `price-axis`, `volume-axis` and `panel-axis-<indicator id>`.
  - Behaviour lives in classes (`ApiClient`, `ThemeController`, `MotionController`, `SceneController` and its subclasses). React components are thin.
  - `AppLayout` wraps every page with the three.js backdrop, the header, a page entrance animation and the chat panel. It shares `/api/status` with pages through the router's outlet context (`layout/layoutContext.ts`).
- **three.js.**
  - `three/candleScene.ts` draws the chart's 3D view: instanced candle bodies, wicks, volume bars and a 20-candle average, with OrbitControls.
  - Every scene subclasses `three/sceneController.ts`, which owns the renderer, camera, animation loop, pause-while-hidden and disposal.
  - Scenes are imported with dynamic `import()` so three.js loads after the first paint.
  - The animation intensity (`maximal`, `reduced`, `off`) comes from `MotionController`, is shown on `<html data-motion>`, and must be respected by every new animation, in CSS as well as in scenes.
- **Theme.** The theme is dark by default; light is chosen with the header toggle and stored in `localStorage`. Colours are CSS custom properties in `styles/tokens.css`, which scenes read through `cssColor`.

## Rules

- **Never write to ubi or its stores.** Never change ubi's code. Never call ubi's `/api/session/connect` when a stored token is usable, because every connect logs out every other ubi client.
- **Keep the Docker network separate.** Containers stay on `instruments_explorer_network`. Never attach them to `unified_broker_interface_network` or any other project's network.
- **Chat assistant.**
  - The default model is `claude-opus-5-5`. Effort is always passed explicitly, because that model defaults to `medium`.
  - Thinking cannot be disabled on it, and forced `tool_choice` is rejected.
  - Conversation history must stay append-only.
  - The API key lives only on the server, in `INSTRUMENTS_EXPLORER_ANTHROPIC_API_KEY`.
- **Knowledge fetchers.**
  - Every new fetcher goes through `PoliteHttpClient`, so it respects robots.txt and the per-host rate limit. Check a new site's robots.txt with Python's `urllib.robotparser` before adding it.
  - Paywalled sites such as Bloomberg and The Economist contribute only their public RSS headlines and summaries.
  - Web search uses official search APIs, never scraped result pages.
  - Never put the user's email address in a user agent or request on your own initiative; Wikipedia's contact value is the user's choice.
- **Browser checks.** Use a throwaway password passed through the environment of a single run, never written to `.env`. The user runs the app as a systemd user service on port 8100, so run the check copy on another port such as 8101 and open it at `127.0.0.1`, not `localhost`. Browser cookies ignore the port, so logging in on `localhost:8101` would log the user out on `localhost:8100`.
- **Restarting.** After backend changes, restart the user's service with `systemctl --user restart instruments-explorer`. A frontend rebuild needs no restart.
- **Sources of truth.** Highcharts is used under its non-commercial licence. The ubi REST reference is `~/Projects/unified_broker_interface/docs/rest-api/`.

## Conventions

These follow the user's global instructions and the sibling projects:

- **Structure.** Code is class-based. Similar cases each get their own class in their own file, with only genuinely identical mechanism in a shallow base class.
- **Docstrings.** Every Python function, method and class has a Google-style docstring with typed `Args:`, `Returns:` and `Raises:`, tests included. Every TypeScript function has a JSDoc comment.
- **No explanatory comments.** Code and config files carry no explanatory comments. Reasoning goes in a sidecar note at `.claude/notes/<same path>.md`.
- **Names.** Names are spelled out in full, such as `explorer_settings` or `canvasReference`.
- **Collections.** Every element of a collection literal goes on its own line.
- **Python imports.** Import modules, not classes (`from instruments_explorer.routes import auth_routes`), one import per line, with single quotes. `ruff.toml` enforces the import style.
- **Commits.** Make one commit per coherent group of changes, explained in plain language, because the user is new to git.
