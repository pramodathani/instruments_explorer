# Instruments Explorer

A web application for exploring every instrument that [unified_broker_interface](../unified_broker_interface) knows about: searching and browsing them, drilling into derivatives, charting them with TA-Lib indicators, screening them, and reading what is known about the companies behind them. A Claude chat assistant can drive the site from plain-language requests.

It runs on this machine next to unified_broker_interface, which it only ever reads. It keeps its own data in its own MongoDB and ChromaDB containers.

## First-time setup

1. Create the Python environment and install the libraries.

   ```bash
   python3.14 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

2. Copy the settings template and fill in the MongoDB password (any long random string).

   ```bash
   cp .env.example .env
   ```

3. Start MongoDB and ChromaDB. They run on their own Docker network, `instruments_explorer_network`, and only listen on 127.0.0.1.

   ```bash
   docker compose up -d --wait
   ```

4. Choose the login password. The script prints two lines; put them in `.env`.

   ```bash
   bin/set-password
   ```

5. Build the frontend.

   ```bash
   source ~/.nvm/nvm.sh
   cd frontend && npm install && npm run build
   ```

6. Start the server and open <http://localhost:8100>.

   ```bash
   bin/instruments-explorer
   ```

The chat assistant stays switched off until `INSTRUMENTS_EXPLORER_ANTHROPIC_API_KEY` is set in `.env`.

## Running it as a service

```bash
systemctl --user link ~/Projects/instruments_explorer/services/instruments-explorer.service
systemctl --user enable --now instruments-explorer
journalctl --user -u instruments-explorer -f
```

## Ports

| Port | What listens |
|---|---|
| 8100 | The web application |
| 5175 | The Vite development server, during frontend work |
| 3003 | The project's MongoDB (127.0.0.1 only) |
| 3004 | The project's ChromaDB (127.0.0.1 only) |

## Development

| Task | Command |
|---|---|
| Tests | `.venv/bin/pytest` |
| Lint and format check | `.venv/bin/ruff check . && .venv/bin/ruff format --check .` |
| Frontend typecheck and build | `cd frontend && npm run build` |
| Frontend with live reload | `cd frontend && npm run dev`, then open <http://localhost:5175> |
