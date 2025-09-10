"""Ingestion backend abstraction (Stage 1 scaling).

Provides a unified interface so we can later plug in Redis or other queue systems.
"""
from __future__ import annotations
import os, asyncio, time, typing as _t
from dataclasses import dataclass

T = _t.TypeVar('T')

class IngestionBackend(_t.Generic[T]):
    name: str = "base"
    supports_depth: bool = True

    async def put(self, item: T) -> None:  # async for future compatibility
        raise NotImplementedError

    def put_nowait(self, item: T) -> None:
        raise NotImplementedError

    def qsize(self) -> int:
        return -1

    async def get(self) -> T:
        raise NotImplementedError

    def get_nowait(self) -> T:
        raise NotImplementedError

class InMemoryBackend(IngestionBackend[T]):
    name = "memory"
    def __init__(self, maxsize: int = 0):
        self._q: asyncio.Queue[T] = asyncio.Queue(maxsize=maxsize)

    async def put(self, item: T) -> None:
        await self._q.put(item)

    def put_nowait(self, item: T) -> None:
        self._q.put_nowait(item)

    def qsize(self) -> int:
        return self._q.qsize()

    async def get(self) -> T:
        return await self._q.get()

    def get_nowait(self) -> T:
        return self._q.get_nowait()

class RedisBackend(IngestionBackend[T]):  # stub for Stage 1 (non-functional placeholder)
    name = "redis"
    supports_depth = False
    def __init__(self):
        self._warned = False

    def _warn(self):
        if not self._warned:
            # Lazy import logging to avoid overhead if unused
            try:
                import logging
                logging.getLogger(__name__).warning("RedisBackend selected but not implemented; falling back to in-memory.")
            except Exception:
                pass
            self._warned = True

    async def put(self, item: T) -> None:  # noqa: D401
        self._warn()
        raise NotImplementedError("Redis backend not implemented yet")

    def put_nowait(self, item: T) -> None:  # noqa: D401
        self._warn()
        raise NotImplementedError("Redis backend not implemented yet")

    def qsize(self) -> int:
        return -1

    async def get(self) -> T:  # noqa: D401
        self._warn()
        raise NotImplementedError("Redis backend not implemented yet")

    def get_nowait(self) -> T:  # noqa: D401
        self._warn()
        raise NotImplementedError("Redis backend not implemented yet")

@dataclass
class BackendSelection:
    backend: IngestionBackend
    fallback: bool
    selected_name: str
    env_requested: str

_cache: BackendSelection | None = None

def select_backend() -> BackendSelection:
    global _cache
    if _cache is not None:
        return _cache
    requested = os.getenv("INGEST_BACKEND", "memory").lower().strip() or "memory"
    fallback = False
    if requested == "memory":
        backend: IngestionBackend = InMemoryBackend()
    elif requested == "redis":
        try:
            backend = RedisBackend()
            # For now we immediately fallback because Redis not implemented
            raise NotImplementedError
        except Exception:
            backend = InMemoryBackend()
            fallback = True
    else:
        backend = InMemoryBackend()
        fallback = True
    _cache = BackendSelection(backend=backend, fallback=fallback, selected_name=backend.name, env_requested=requested)
    return _cache

__all__ = [
    'IngestionBackend', 'InMemoryBackend', 'RedisBackend', 'select_backend', 'BackendSelection'
]
