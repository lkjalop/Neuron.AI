"""Postgres (Neon) async client stub with lazy initialization.

Uses asyncpg if available; otherwise raises on first query attempt.
"""
from __future__ import annotations

import os, asyncio
from typing import Optional, Any, List

_POOL = None
_LOCK = asyncio.Lock()


async def _init_pool():
    global _POOL
    if _POOL is not None:
        return _POOL
    dsn = os.getenv("NEON_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("NEON_DATABASE_URL not set")
    try:
        import asyncpg  # type: ignore
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("asyncpg not installed; add to requirements.txt") from e
    _POOL = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    return _POOL


async def fetch(sql: str, *args) -> List[Any]:
    pool = await _init_pool()
    async with pool.acquire() as conn:  # type: ignore
        return await conn.fetch(sql, *args)  # type: ignore


async def execute(sql: str, *args) -> Any:
    pool = await _init_pool()
    async with pool.acquire() as conn:  # type: ignore
        return await conn.execute(sql, *args)  # type: ignore

async def executemany(sql: str, rows: List[tuple]) -> Any:
    pool = await _init_pool()
    async with pool.acquire() as conn:  # type: ignore
        try:
            return await conn.executemany(sql, rows)  # type: ignore
        except Exception:
            # Best-effort fallback: sequential execute
            for r in rows:
                try:
                    await conn.execute(sql, *r)  # type: ignore
                except Exception:
                    continue
            return None


async def health() -> bool:
    try:
        rows = await fetch("SELECT 1")
        return bool(rows)
    except Exception:
        return False


__all__ = ["fetch", "execute", "health"]
__all__.append("executemany")
