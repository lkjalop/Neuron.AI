from __future__ import annotations
"""App Factory

Provides a centralized FastAPI app constructor so tests and services can
instantiate a minimal or full-featured application without importing a
monolithic module. This enables:
  - Faster unit tests (omit heavy routers)
  - Feature flag style inclusion of optional subsystems
  - Cleaner layering for future graph / GNN integration
"""
from typing import Iterable
from fastapi import FastAPI
import asyncio
import os
import json
from pathlib import Path

FEATURE_REFRESH_INTERVAL = float(os.environ.get("GRAPH_FEATURE_REFRESH_SEC", "60"))

OPTIONAL_ROUTERS: dict[str, str] = {
    'intel_timeline': 'api.routers.intel_timeline',
    'feedback': 'api.routers.feedback',
    'explain': 'api.routers.explain',
    'graph': 'api.routers.graph',
}
CORE_ROUTERS: dict[str, str] = {
    'enrichment': 'api.routers.enrichment',
}

def _import_router(module_path: str):  # pragma: no cover - tiny helper
    mod = __import__(module_path, fromlist=['router'])
    return getattr(mod, 'router', None)

def create_app(include_optional: bool = True, include: Iterable[str] | None = None, exclude: Iterable[str] | None = None) -> FastAPI:
    """Create and configure FastAPI application.

    Args:
      include_optional: include all optional routers unless explicitly excluded.
      include: explicit list of router keys to include (overrides include_optional).
      exclude: list of router keys to skip.
    """
    app = FastAPI(title="Neuron Vulnerability API", version="0.2.0")

    # Core routers
    for key, path in CORE_ROUTERS.items():
        try:
            r = _import_router(path)
            if r:
                app.include_router(r)
        except Exception:
            continue

    wanted_optional = set(OPTIONAL_ROUTERS.keys()) if include_optional else set()
    if include is not None:
        wanted_optional = set(include)
    if exclude is not None:
        wanted_optional = {w for w in wanted_optional if w not in set(exclude)}

    for key in sorted(wanted_optional):
        path = OPTIONAL_ROUTERS.get(key)
        if not path:
            continue
        try:
            r = _import_router(path)
            if r:
                app.include_router(r)
        except Exception:
            continue

    # Background feature refresh (graph intelligence scaffold)
    try:
        from graph.features import refresh_features  # type: ignore
    except Exception:  # pragma: no cover
        refresh_features = None  # type: ignore

    if refresh_features:
        async def _periodic_refresh():  # pragma: no cover - timing logic
            while True:
                try:
                    refresh_features()
                    # Persist snapshot (best-effort)
                    try:
                        from graph.relationships import get_graph  # type: ignore
                        from graph.features import get_features, get_feature_metadata  # type: ignore
                        g = get_graph()
                        snapshot = g.export()
                        snapshot["features"] = get_features()
                        snapshot["features_meta"] = get_feature_metadata()
                        Path("artifacts").mkdir(exist_ok=True)
                        with open("artifacts/runtime_graph.json", "w", encoding="utf-8") as f:
                            json.dump(snapshot, f, indent=2)
                    except Exception:
                        pass
                except Exception:
                    pass
                await asyncio.sleep(FEATURE_REFRESH_INTERVAL)

        @app.on_event("startup")
        async def _start_feature_task():  # pragma: no cover
            asyncio.create_task(_periodic_refresh())

    return app

__all__ = ["create_app"]