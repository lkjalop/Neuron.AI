"""Temporal feature store writer/reader stubs.

This module provides a minimal interface for persisting temporal feature
vectors used by predictive / emergence models. Designed to remain thin and
asyncpg-agnostic – it calls the generic storage.postgres helper.

Table: feature_series (migration 0007)
Columns:
  id (TEXT PK) – caller-provided or generated
  asset_id (TEXT) – asset key
  kind (TEXT) – feature namespace (e.g., 'risk.window', 'snn.embedding')
  ts (DOUBLE) – event timestamp (epoch seconds)
  vector (JSONB) – arbitrary JSON structure (list/obj)
  version (INT) – schema version of vector

Future enhancements:
 - TTL / compaction (retain last N per (asset,kind))
 - Downsampling (EMA or reservoir sampling)
 - Batch fetch for model training / online scoring windows
"""
from __future__ import annotations

import time
import hashlib
from typing import Any, Dict, List, Optional

from storage import postgres  # type: ignore

__all__ = ["write_feature", "list_recent_features"]


def _gen_id(asset_id: str, kind: str, ts: float) -> str:
    base = f"feat-{asset_id}-{kind}-{int(ts*1000)}"
    return hashlib.sha256(base.encode()).hexdigest()[:40]


async def write_feature(asset_id: str, kind: str, vector: Any, ts: Optional[float] = None, *, version: int = 1, feature_id: str | None = None) -> str:
    ts = ts or time.time()
    fid = feature_id or _gen_id(asset_id, kind, ts)
    try:
        await postgres.execute(
            """
            INSERT INTO feature_series (id, asset_id, kind, ts, vector, version)
            VALUES ($1,$2,$3,$4,$5,$6)
            ON CONFLICT (id) DO UPDATE SET
              vector=EXCLUDED.vector,
              version=EXCLUDED.version
            """,
            fid,
            asset_id,
            kind,
            float(ts),
            vector,
            version,
        )
    except Exception:
        # best-effort
        pass
    return fid


async def list_recent_features(asset_id: str, kind: str, limit: int = 50) -> List[Dict[str, Any]]:
    if limit <= 0:
        return []
    try:
        rows = await postgres.fetch(
            """
            SELECT id, ts, vector, version FROM feature_series
            WHERE asset_id=$1 AND kind=$2
            ORDER BY ts DESC LIMIT $3
            """,
            asset_id,
            kind,
            limit,
        )
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for r in rows:
        try:
            out.append({"id": r[0], "ts": r[1], "vector": r[2], "version": r[3]})
        except Exception:
            continue
    return out
