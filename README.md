# Xian Playground

An interactive Reflex-based web playground for the Xian Contracting engine. Users can author, lint, deploy, and call smart contracts directly in the browser while the backend runs a full `xian-contracting` runtime per session.

## Prerequisites

- Python **3.11** (strictly required by the local `pyproject.toml` and `xian-contracting`).
- [Poetry](https://python-poetry.org/docs/#installation) for dependency management.
- Node.js ≥ 18 **or** Bun ≥ 1.1 (Reflex builds the React frontend via whichever runtime is on your `PATH`).
- A compiler toolchain for any transitive dependencies (e.g., system `make`, `gcc`, `pkg-config`).

## Configuration

Runtime settings are declared directly in `rxconfig.py`. By default the playground
assumes the public origin `https://playground.xian.technology`, serves the frontend
on port `3000`, the backend on `8000`, and disables SSR (`REFLEX_SSR=0`) to avoid
hydration flicker behind the reverse proxy. If you need to change any value,
edit `rxconfig.py` (or export the matching environment variable before launching).

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

- Frontend: serves the precompiled React bundle via Sirv on port **3000**.
- Backend: Granian/ASGI server on port **8000**.
- Keep this process alive (or run it via `systemd`; see below). If either port is already bound you will see a startup error.

### Development mode

```bash
poetry run reflex run --env dev
```

This launches the Vite dev server with hot reload and a single backend worker on whatever open ports Reflex negotiates.

## Reverse proxy / deployment notes

- Behind Nginx, send **all** paths to the frontend on port 3000 *except* the backend helpers (`/_event`, `/sessions`). Those must be proxied to port 8000 with `proxy_http_version 1.1`, `Upgrade`, and `Connection "upgrade"` headers so the Reflex websocket works.
- Add a CSP header that includes `'unsafe-eval'` in `script-src`. Reflex bundles (Monaco, Radix) rely on `new Function`, and blocking it causes hydration failures.
- All session state (contract storage, metadata, UI snapshots) lives under `playground/.sessions/`. Ensure the runtime user can read/write this directory and monitor it for growth.
- Do **not** set `REFLEX_REDIS_URL` unless you also add cross-process locking. The playground’s session manager is intentionally single-process; Redis would cause Reflex to spawn multiple workers and corrupt the per-session filesystem state.

### Example Nginx config (single-port mode)

```nginx
  GNU nano 7.2                                                              /etc/nginx/sites-available/playground.xian.technology
server
{
        server_name playground.xian.technology;

        location /
        {
                proxy_pass http://127.0.0.1:8001;
                proxy_http_version 1.1;
                proxy_set_header Upgrade $http_upgrade;
                proxy_set_header Connection "upgrade";
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
        }

        listen 443 ssl;
        ssl_certificate /etc/letsencrypt/live/xian.technology/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/xian.technology/privkey.pem;
        include /etc/letsencrypt/options-ssl-nginx.conf;
        ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}

server
{
        if ($host = playground.xian.technology)
        {
                return 301 https://$host$request_uri;
        }
        listen 80;
        server_name playground.xian.technology;
        return 404;
}
```

Reload Nginx after editing: `sudo nginx -s reload`.

> **Note:** The commands above assume the Reflex service is running with `poetry run reflex run --env prod --single-port --frontend-port 8001 --backend-port 8001`. Adjust the port if you choose a different one.

### systemd unit

To keep the playground running after boot, install a service such as:
`/etc/systemd/system/xian-playground.service`

```
[Unit]
Description=Xian Playground
After=network.target

[Service]
Type=simple
User=endogen
WorkingDirectory=/home/endogen/xian-playground
Environment="PATH=/home/endogen/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/home/endogen/.cache/pypoetry/virtualenvs/xian-playground--o3SVNIl-py3.11/bin"
ExecStart=/home/endogen/.local/bin/poetry run reflex run --env prod --single-port --frontend-port 8001 --backend-port 8001
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```
sudo systemctl daemon-reload
sudo systemctl enable --now xian-playground
```

Use `journalctl -u xian-playground -f` to follow logs.

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
