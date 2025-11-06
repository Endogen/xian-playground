# Xian Playground

An interactive Reflex-based web playground for the Xian Contracting engine. Users can author, lint, deploy, and call smart contracts directly in the browser while the backend runs a full `xian-contracting` runtime per session.

## Prerequisites

- Python **3.11** (strictly required by the local `pyproject.toml` and `xian-contracting`).
- [Poetry](https://python-poetry.org/docs/#installation) for dependency management.
- Node.js ≥ 18 **or** Bun ≥ 1.1 (Reflex builds the React frontend via whichever runtime is on your `PATH`).
- A compiler toolchain for any transitive dependencies (e.g., system `make`, `gcc`, `pkg-config`).

## Configuration

1. Copy the example environment file and adjust values for your deployment:

   ```bash
   cp .env.example .env
   ```

2. Set the following keys (all are required because `rxconfig.py` validates them on import):

   | Key | Description | Typical Value |
   | --- | ----------- | ------------- |
   | `REFLEX_FRONTEND_PORT` | Port the compiled React app listens on. | `3001` |
   | `REFLEX_BACKEND_PORT` | Port for the ASGI backend (Gunicorn/Granian). | `8000` |
   | `REFLEX_DEPLOY_URL` | Public HTTPS origin for the UI. | `https://playground.xian.technology` |
   | `REFLEX_API_URL` | Public HTTPS origin the frontend uses for events/API. | `https://playground.xian.technology` |
   | `PLAYGROUND_SESSION_COOKIE_SECURE` | `1` to set the `Secure` flag on session cookies when fronted by TLS. | `1` |

Keep `.env` out of version control; only `.env.example` is tracked.

## Installation

```bash
poetry install
```

This installs the Reflex app plus the editable `xian-contracting` package located in the `xian-contracting/` subdirectory.

## Running the app

### Production mode (recommended, matches server behavior)

```bash
poetry run reflex run --env prod
```

- Frontend: serves the precompiled React bundle via Sirv on `REFLEX_FRONTEND_PORT` (default `3001`).
- Backend: runs Gunicorn+Uvicorn (or Granian if Gunicorn isn’t available) on `REFLEX_BACKEND_PORT` (default `8000`).
- The command expects both ports to be free. Use `--single-port` if you prefer the backend to host the compiled frontend itself, e.g. `poetry run reflex run --env prod --single-port --frontend-port 3001`.

### Development mode

```bash
poetry run reflex run --env dev
```

This launches the Vite dev server with hot reload and a single backend worker on whatever open ports Reflex negotiates.

## Reverse proxy / deployment notes

- Behind Nginx or another reverse proxy, forward the HTTPS origin (`https://playground.xian.technology`) to the frontend port and proxy API/WebSocket routes (`/_event`, `/_upload`, `/sessions`, etc.) to the backend port. Remember to pass `Upgrade`/`Connection` headers for WebSockets.
- All session state (contract storage, metadata, UI snapshots) lives under `playground/.sessions/`. Ensure the runtime user can read/write this directory and monitor it for growth.
- Do **not** set `REFLEX_REDIS_URL` unless you also add cross-process locking. The playground’s session manager is intentionally single-process; Redis would cause Reflex to spawn multiple workers and corrupt the per-session filesystem state.

## Testing

Run the fast unit suite before committing changes:

```bash
poetry run pytest tests/unit
```

Use `poetry run pytest tests/integration -k <pattern>` when touching runtime, storage, or session logic.

## Troubleshooting

- Missing env vars: `rxconfig.py` raises a `RuntimeError` naming the missing key. Double-check `.env`.
- Frontend build errors: verify Node/Bun are installed and run `poetry run reflex run --env prod --frontend-only` to see the raw logs inside `.web/`.
- Session cookie not set: confirm `PLAYGROUND_SESSION_COOKIE_SECURE=1` when serving through HTTPS; browsers discard insecure cookies on secure origins.

With the prerequisites satisfied and `.env` configured, the playground can be started locally or deployed on a server by copying the repository and running the single command `poetry run reflex run --env prod`. Front the two internal ports with your preferred process manager and reverse proxy to make it available at `https://playground.xian.technology`.
