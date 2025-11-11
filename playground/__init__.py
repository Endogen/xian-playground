"""Xian Contracting web playground package."""

from __future__ import annotations

__all__ = ["app"]


def __getattr__(name: str):
    if name == "app":
        from .playground import app as _app

        return _app
    raise AttributeError(name)
