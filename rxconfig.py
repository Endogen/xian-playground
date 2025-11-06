"""Reflex runtime configuration for the playground app."""

from __future__ import annotations

import os
from pathlib import Path

import reflex as rx


def _bootstrap_env_file(path: str = ".env") -> None:
    """Populate os.environ with variables defined in the local .env file."""
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _require_env(key: str) -> str:
    """Return the value of `key` or raise a helpful error if missing."""
    value = os.getenv(key)
    if value is None or value.strip() == "":
        raise RuntimeError(
            f"{key} is not set. Ensure it exists in your .env file or environment."
        )
    return value


_bootstrap_env_file()


config = rx.Config(
    app_name="playground",
    deploy_url=_require_env("REFLEX_DEPLOY_URL"),
    api_url=_require_env("REFLEX_API_URL"),
    frontend_port=int(_require_env("REFLEX_FRONTEND_PORT")),
    backend_port=int(_require_env("REFLEX_BACKEND_PORT")),
    env_file=".env",
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
)
