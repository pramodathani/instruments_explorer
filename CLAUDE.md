# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

instruments_explorer is a password-protected web application for exploring the instruments that the sibling project unified_broker_interface (ubi, `~/Projects/unified_broker_interface`) knows about. It shows instruments, quotes, candles and TA-Lib indicators taken from ubi, together with company data that it downloads from the internet and stores in its own MongoDB and ChromaDB. It also has a Claude chat assistant that can drive the site. The stack and conventions are copied from the sibling projects `sridhara` and `system_monitor`.

The full, approved build plan is in `~/.claude/plans/there-is-a-sibling-starry-lagoon.md`. The work is split into eight phases, and phase 1 (the scaffold) is done:

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
- **ubi (from phase 2).** ubi is reached only through its published host ports: the REST API at 127.0.0.1:8080 and Redis at port 1002. The access token comes from ubi's stored login, following sridhara's `AccessTokenProvider`.
- **Frontend** (`frontend/`). React 19, TypeScript 7, Vite 8 and react-router 8, with three.js and Highcharts / Highcharts Stock.
  - Behaviour lives in classes (`ApiClient`, `ThemeController`, `MotionController`, `SceneController` and its subclasses). React components are thin.
  - `AppLayout` wraps every page with the three.js backdrop, the header, a page entrance animation and the chat panel. It shares `/api/status` with pages through the router's outlet context (`layout/layoutContext.ts`).
- **three.js.**
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
  - Fetchers respect robots.txt and a per-host rate limit.
  - Paywalled sites such as Bloomberg and The Economist contribute only their public RSS headlines and summaries.
  - Web search uses official search APIs, never scraped result pages.
- **Browser checks.** Use a throwaway password passed through the environment of a single run, never written to `.env`.
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
