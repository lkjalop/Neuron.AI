"""App factory shim for tests expecting core.app_factory.create_app.

Some tests import `create_app` from `core.app_factory`. The main application
assembly currently lives in `core.main` (where a FastAPI instance named `app`
is constructed). To avoid duplicating initialization logic (routers, events,
background tasks), we provide a thin wrapper that returns the already-built
`app` object from `core.main`.

If in the future we need a true factory (e.g., parameterizing feature flags or
injecting test doubles), we can expand this module to build a fresh FastAPI
instance on each call. For now, returning the singleton keeps behavior
unchanged while unblocking the test suite.
"""
from __future__ import annotations

from fastapi import FastAPI  # type: ignore

# Import the existing app assembled in core.main
try:
    from core.main import app as _main_app  # noqa: F401
except Exception as exc:  # pragma: no cover - defensive
    raise RuntimeError(f"Failed to import core.main.app: {exc}") from exc


def create_app() -> FastAPI:
    """Return the already-initialized FastAPI application.

    Returns:
        FastAPI: The singleton FastAPI app defined in core.main.
    """
    return _main_app
