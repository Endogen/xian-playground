"""Reflex runtime configuration for the playground app."""

from __future__ import annotations

import reflex as rx


config = rx.Config(
    app_name="playground",
    deploy_url="https://playground.xian.technology",
    api_url="https://playground.xian.technology",
    frontend_port=3000,
    backend_port=8000,
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
)
