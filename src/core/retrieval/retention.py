"""Retention policy for retrieval_chunks SQLite table.

Prunes rows by max row count and age. Emits metrics:
  - neuron_retrieval_retention_purged_total{reason}
  - neuron_retrieval_chunks_rows
  - neuron_retrieval_chunk_text_bytes_total
Runtime params (optional):
  retrieval.retention.max_rows (default 50000)
  retrieval.retention.max_age_hours (default 168; set 0/None to disable age prune)
"""
from __future__ import annotations
import os, sqlite3, time, math
from typing import Optional

_SQLITE_PATH = os.getenv("SQLITE_DB_PATH", "artifacts/neuron.db")

try:
    from core.metrics import (
        RETRIEVAL_RETENTION_PURGED_TOTAL,
        RETRIEVAL_CHUNKS_ROWS,
        RETRIEVAL_CHUNK_TEXT_BYTES,
    )  # type: ignore
except Exception:  # pragma: no cover
    RETRIEVAL_RETENTION_PURGED_TOTAL = None  # type: ignore
    RETRIEVAL_CHUNKS_ROWS = None  # type: ignore
    RETRIEVAL_CHUNK_TEXT_BYTES = None  # type: ignore

try:
    from config import runtime_params  # type: ignore
except Exception:  # pragma: no cover
    runtime_params = None  # type: ignore


def _rp(name: str, default):
    try:
        if runtime_params is None:
            return default
        v = runtime_params.get_param(name)
        return default if v is None else v
    except Exception:
        return default


def prune_retrieval_chunks(max_rows: Optional[int] = None, max_age_hours: Optional[int] = None) -> dict:
    if not _SQLITE_PATH:
        return {"error": "no_sqlite_path"}
    max_rows = int(_rp("retrieval.retention.max_rows", max_rows if max_rows is not None else 50000))
    max_age_hours = _rp("retrieval.retention.max_age_hours", max_age_hours if max_age_hours is not None else 168)
    if max_age_hours is not None:
        try:
            max_age_hours = int(max_age_hours)
        except Exception:
            max_age_hours = 168
    purged_rows = 0
    purged_age = 0
    now = time.time()
    try:
        conn = sqlite3.connect(_SQLITE_PATH)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS retrieval_chunks (id TEXT PRIMARY KEY, doc TEXT, chunk_id INT, hash TEXT, text TEXT, length INT, tenant TEXT, created_ts REAL)")
        # Row count
        cur.execute("SELECT COUNT(*), COALESCE(SUM(length),0) FROM retrieval_chunks")
        row = cur.fetchone()
        total_rows = int(row[0]) if row else 0
        total_bytes = int(row[1]) if row else 0
        # Age prune
        if max_age_hours and max_age_hours > 0:
            cutoff = now - max_age_hours * 3600
            cur.execute("DELETE FROM retrieval_chunks WHERE created_ts < ?", (cutoff,))
            purged_age = cur.rowcount
        # Over-cap prune (delete oldest beyond threshold)
        if total_rows - purged_age > max_rows:
            # Determine number to remove after age deletion
            to_remove = (total_rows - purged_age) - max_rows
            cur.execute("SELECT id FROM retrieval_chunks ORDER BY created_ts ASC LIMIT ?", (to_remove,))
            ids = [r[0] for r in cur.fetchall()]
            if ids:
                cur.executemany("DELETE FROM retrieval_chunks WHERE id = ?", [(i,) for i in ids])
                purged_rows = cur.rowcount
        conn.commit()
        # Recompute counts
        cur.execute("SELECT COUNT(*), COALESCE(SUM(length),0) FROM retrieval_chunks")
        row2 = cur.fetchone()
        new_total = int(row2[0]) if row2 else 0
        new_bytes = int(row2[1]) if row2 else 0
        conn.close()
        # Metrics
        try:
            if RETRIEVAL_CHUNKS_ROWS is not None:
                RETRIEVAL_CHUNKS_ROWS.set(new_total)
            if RETRIEVAL_CHUNK_TEXT_BYTES is not None:
                RETRIEVAL_CHUNK_TEXT_BYTES.set(new_bytes)
            if RETRIEVAL_RETENTION_PURGED_TOTAL is not None:
                if purged_rows:
                    RETRIEVAL_RETENTION_PURGED_TOTAL.labels(reason="rows").inc(purged_rows)
                if purged_age:
                    RETRIEVAL_RETENTION_PURGED_TOTAL.labels(reason="age").inc(purged_age)
        except Exception:
            pass
        return {
            "purged_rows": purged_rows,
            "purged_age": purged_age,
            "remaining_rows": new_total,
            "remaining_bytes": new_bytes,
        }
    except Exception as e:  # pragma: no cover
        return {"error": str(e)}

__all__ = ["prune_retrieval_chunks"]
