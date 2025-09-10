"""Rolling window feature extractor.

Generates feature windows from recent findings for use with reservoir embeddings
and drift calculations.

API:
  async load_recent_findings(asset_id: str | None, since_ts: float) -> list[dict]
  async build_feature_window(asset_id: str | None, horizon_hours: int = 24, bucket_minutes: int = 60) -> list[list[float]]

Current feature vector schema (per bucket):
  [ new_findings_count, high_sev_count, exploit_flag_count, kev_listed_count ]

Future extensions: add mean risk score, closure count, remediation velocity.
"""
from __future__ import annotations

import time
from typing import List, Dict, Any, Optional

from storage import postgres  # type: ignore

async def load_recent_findings(asset_id: str | None, since_ts: float) -> List[Dict[str, Any]]:
    clauses = ["last_seen >= $1"]
    args: List[Any] = [since_ts]
    if asset_id:
        clauses.append("asset_id = $%d" % (len(args)+1))
        args.append(asset_id)
    where = " WHERE " + " AND ".join(clauses)
    sql = f"SELECT id, risk_severity, risk_score, sla_due_ts, cve_id, risk_factors, last_seen FROM findings{where}"
    rows = await postgres.fetch(sql, *args)
    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        out.append(d)
    return out

async def build_feature_window(asset_id: str | None, horizon_hours: int = 24, bucket_minutes: int = 60) -> List[List[float]]:
    now = time.time()
    horizon_s = horizon_hours * 3600
    since = now - horizon_s
    rows = await load_recent_findings(asset_id, since)
    bucket_s = bucket_minutes * 60
    bucket_count = max(1, int(horizon_s / bucket_s))
    # Initialize buckets
    buckets = [dict(new=0, high=0, exploit=0, kev=0) for _ in range(bucket_count)]
    for f in rows:
        ts = float(f.get("last_seen") or now)
        if ts < since:
            continue
        idx = int((ts - since) / bucket_s)
        if idx >= bucket_count:
            idx = bucket_count - 1
        b = buckets[idx]
        b["new"] += 1
        sev = (f.get("risk_severity") or "").upper()
        if sev in {"HIGH", "CRITICAL"}:
            b["high"] += 1
        rf = f.get("risk_factors") or {}
        if isinstance(rf, dict):
            if rf.get("exploit_available") or rf.get("exploit_component"):
                b["exploit"] += 1
            if rf.get("kev_listed"):
                b["kev"] += 1
    # Convert to ordered numeric vectors
    vectors: List[List[float]] = []
    for b in buckets:
        vectors.append([
            float(b["new"]),
            float(b["high"]),
            float(b["exploit"]),
            float(b["kev"]),
        ])
    return vectors

__all__ = ["build_feature_window", "load_recent_findings"]
