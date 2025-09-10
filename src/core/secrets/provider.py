"""Secret provider abstraction.

Provides a minimal pluggable interface so future backends (Vault, AWS SM, GCP
Secret Manager) can be integrated without changing call sites.

Usage:
    from core.secrets.provider import get_secret
    token = await get_secret("API_TOKEN")  # async for future parity; env is sync

Design:
 - Async interface even for env backend to keep future compatibility.
 - Simple in-memory LRU (optional) could be added later if backends have rate limits.
 - Fallback order: explicit backend (env var SECRET_BACKEND), else environment.

Runtime Params (future): could map secret names to backend IDs; for now single backend.
"""
from __future__ import annotations

import os
from typing import Optional, Protocol, runtime_checkable, Dict, Any

@runtime_checkable
class SecretBackend(Protocol):
    async def get(self, name: str) -> Optional[str]: ...  # noqa: D401,E701


class EnvSecretBackend:
    """Environment variable based backend."""
    async def get(self, name: str) -> Optional[str]:  # noqa: D401
        return os.getenv(name)


_BACKENDS: Dict[str, SecretBackend] = {
    "env": EnvSecretBackend(),
}

_default_backend_name = os.getenv("SECRET_BACKEND", "env")


def register_backend(name: str, backend: SecretBackend) -> None:
    _BACKENDS[name] = backend


async def get_secret(name: str, *, backend: str | None = None, default: Optional[str] = None) -> Optional[str]:
    bname = backend or _default_backend_name
    b = _BACKENDS.get(bname)
    if not b:
        b = _BACKENDS["env"]
    try:
        v = await b.get(name)
        if v is None:
            return default
        return v
    except Exception:
        return default

__all__ = ["get_secret", "register_backend", "SecretBackend"]
