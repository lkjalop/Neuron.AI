"""Connector stubs for external data sources.

Real implementations will map vendor-specific records into internal Event objects.
Refer to docs/CONNECTORS.md for design principles.
"""

from __future__ import annotations

# Connector registry supports dynamic discovery; values can be callables or classes.
CONNECTOR_REGISTRY = {}

def register(name: str):
    def deco(obj):
        CONNECTOR_REGISTRY[name] = obj
        return obj
    return deco

# Re-export Qualys & Tenable skeletons
try:  # pragma: no cover - optional import safeguard
    from .qualys import qualys_stream, QualysConfig
    register("qualys.stream")(qualys_stream)
except Exception:  # noqa: broad-except
    pass
try:  # pragma: no cover
    from .tenable import tenable_stream, TenableConfig
    register("tenable.stream")(tenable_stream)
except Exception:  # noqa: broad-except
    pass
try:  # pragma: no cover
    from .siem import siem_stream, SIEMConfig
    register("siem.stream")(siem_stream)
except Exception:  # noqa: broad-except
    pass

__all__ = [
    "CONNECTOR_REGISTRY",
    "register",
    "qualys_stream",
    "QualysConfig",
    "tenable_stream",
    "TenableConfig",
    "siem_stream",
    "SIEMConfig",
]

