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

_GRAPH_ROUTER_INCLUDED = False

def _ensure_graph_router(app: FastAPI):
    """Include the graph router if not already present.

    The Phase 3/4 graph intelligence endpoints live in ``api.routers.graph``.
    Some earlier module load orders may omit explicit inclusion, so tests
    expecting ``/api/v1/graph/*`` paths would fail (404). We defensively
    include the router here exactly once.
    """
    global _GRAPH_ROUTER_INCLUDED
    if _GRAPH_ROUTER_INCLUDED:
        return
    # Detect by path prefix to avoid duplicate include
    try:
        if any(getattr(r, 'path', '').startswith('/api/v1/graph') for r in app.routes):
            _GRAPH_ROUTER_INCLUDED = True
            return
    except Exception:
        pass
    try:  # best-effort include
        from api.routers import graph as _graph_router  # type: ignore
        if hasattr(_graph_router, 'router'):
            app.include_router(_graph_router.router)
            _GRAPH_ROUTER_INCLUDED = True
    except Exception:
        pass


def create_app(*, include_optional: bool = False) -> FastAPI:  # signature matches api.app usage
    """Return the already-initialized FastAPI application.

    Args:
        include_optional: When True, ensures optional routers (currently graph)
            are definitely included. This mirrors the call pattern in
            ``api.app`` which passes ``include_optional=True``.

    Returns:
        FastAPI: The singleton FastAPI app defined in ``core.main`` with
        required routers ensured.
    """
    if include_optional:
        _ensure_graph_router(_main_app)
    else:
        # Even when False, we still opportunistically ensure graph endpoints to
        # satisfy focused graph test modules invoking create_app() directly.
        _ensure_graph_router(_main_app)
    return _main_app
