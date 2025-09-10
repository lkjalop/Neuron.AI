"""Risk acceptance / exception tracking helpers.

Provides ability to record a formal exception for a finding for governance reporting.

Schema (migration TBD if not already existing):
  exceptions (
     id TEXT PRIMARY KEY,
     finding_id TEXT REFERENCES findings(id) ON DELETE CASCADE,
     created_ts DOUBLE PRECISION,
     expires_ts DOUBLE PRECISION,
     reason TEXT,
     approved_by TEXT,
     status TEXT  -- active, expired, revoked
  )

We add the table via migration 0010.
"""
from __future__ import annotations

import time
import uuid
from typing import Optional, Dict, Any, List

from storage import postgres  # type: ignore

async def create_exception(finding_id: str, reason: str, approved_by: str, ttl_days: float | None = None) -> str:
    now = time.time()
    expires = None
    if ttl_days is not None:
        try:
            expires = now + float(ttl_days) * 86400.0
        except Exception:
            expires = None
    ex_id = f"exc-{uuid.uuid4()}"
    await postgres.execute(
        """
        INSERT INTO exceptions (id, finding_id, created_ts, expires_ts, reason, approved_by, status)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        """,
        ex_id, finding_id, now, expires, reason, approved_by, "active"
    )
    return ex_id

async def revoke_exception(exception_id: str, note: str | None = None):
    row = await postgres.fetch("SELECT id, status FROM exceptions WHERE id=$1", exception_id)
    if not row:
        return False
    await postgres.execute("UPDATE exceptions SET status='revoked' WHERE id=$1", exception_id)
    if note:
        await postgres.execute(
            """INSERT INTO exception_events (id, exception_id, event_ts, event_type, payload)
            VALUES ($1,$2,$3,$4,$5)""",
            f"exevt-{exception_id}-{int(time.time())}", exception_id, time.time(), "revoked", note
        )
    return True

async def list_active_exceptions(finding_id: str) -> List[Dict[str, Any]]:
    rows = await postgres.fetch(
        "SELECT * FROM exceptions WHERE finding_id=$1 AND status='active'", finding_id
    )
    return [dict(r) for r in rows]

async def expire_exceptions():
    now = time.time()
    rows = await postgres.fetch("SELECT id, expires_ts FROM exceptions WHERE status='active' AND expires_ts IS NOT NULL AND expires_ts < $1", now)
    for r in rows:
        try:
            await postgres.execute("UPDATE exceptions SET status='expired' WHERE id=$1", r[0])
        except Exception:
            continue

__all__ = [
    "create_exception",
    "revoke_exception",
    "list_active_exceptions",
    "expire_exceptions",
]
