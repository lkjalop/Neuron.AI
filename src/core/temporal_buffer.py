"""Temporal buffer store and helpers (extracted from core.main).

Provides a simple per-tenant temporal feature buffer with pruning, capacity,
and readiness metrics hooks. Routers should import these helpers rather than
re-implementing logic.
"""
from __future__ import annotations
import time
from typing import Dict, List

try:
    from core import metrics  # type: ignore
except Exception:  # pragma: no cover
    metrics = None  # type: ignore

# State
TEMPORAL_BUFFER: Dict[str, List[dict]] = {}
TEMPORAL_BUFFER_MAX = 1000
TEMPORAL_BUFFER_READINESS_THRESHOLD = 25
TEMPORAL_BUFFER_RETENTION_S = 3600  # 1h

def prune(tenant: str, now_ts: float | None = None) -> None:
    """Prune expired entries and enforce capacity for a tenant buffer.

    Emits metrics if the core.metrics facade is available; best-effort only.
    """
    buf = TEMPORAL_BUFFER.get(tenant)
    if not buf:
        return
    now_ts = now_ts or time.time()
    cutoff = now_ts - TEMPORAL_BUFFER_RETENTION_S
    original_len = len(buf)
    # Drop old
    buf[:] = [r for r in buf if r.get('ts', 0) >= cutoff]
    dropped = original_len - len(buf)
    if dropped:
        try: metrics.TEMPORAL_BUFFER_PRUNES_TOTAL.labels(tenant=tenant, reason="retention").inc()  # type: ignore[attr-defined]
        except Exception: pass
    # Capacity
    if len(buf) > TEMPORAL_BUFFER_MAX:
        overflow = len(buf) - TEMPORAL_BUFFER_MAX
        del buf[:overflow]
        try: metrics.TEMPORAL_BUFFER_PRUNES_TOTAL.labels(tenant=tenant, reason="capacity").inc(overflow)  # type: ignore[attr-defined]
        except Exception: pass
    # Optional compaction (simple stride down-sample)
    retained_ratio = 1.0
    try:
        from config import runtime_params as _rp  # type: ignore
        max_factor = float(_rp.get_param("temporal.buffer.compaction.max_factor") or 4.0)
        target_factor = float(_rp.get_param("temporal.buffer.compaction.target_factor") or 2.5)
    except Exception:
        max_factor, target_factor = 4.0, 2.5
    if max_factor > 1.0 and target_factor > 1.0 and TEMPORAL_BUFFER_READINESS_THRESHOLD > 0:
        limit = int(TEMPORAL_BUFFER_READINESS_THRESHOLD * max_factor)
        target = int(TEMPORAL_BUFFER_READINESS_THRESHOLD * target_factor)
        if len(buf) > limit and target < len(buf):
            pre_len = len(buf)
            target = max(1, target)
            stride = max(1, pre_len // target)
            buf[:] = buf[::stride][-target:]
            pruned = pre_len - len(buf)
            if pruned > 0:
                try: metrics.TEMPORAL_BUFFER_PRUNES_TOTAL.labels(tenant=tenant, reason="compaction").inc(pruned)  # type: ignore[attr-defined]
                except Exception: pass
            if pre_len > 0:
                retained_ratio = len(buf) / pre_len
    # Gauges
    try:
        metrics.TEMPORAL_BUFFER_SIZE.labels(tenant=tenant).set(len(buf))  # type: ignore[attr-defined]
        metrics.TEMPORAL_BUFFER_READY.labels(tenant=tenant).set(1 if len(buf) >= TEMPORAL_BUFFER_READINESS_THRESHOLD else 0)  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        if hasattr(metrics, 'TEMPORAL_BUFFER_RETAINED_RATIO'):
            metrics.TEMPORAL_BUFFER_RETAINED_RATIO.labels(tenant=tenant).set(retained_ratio)  # type: ignore[attr-defined]
    except Exception:
        pass

def ingest(tenant: str, features: dict) -> int:
    """Append a feature record for a tenant and prune; returns new buffer size."""
    now_ts = time.time()
    rec = {"ts": now_ts, "features": features}
    buf = TEMPORAL_BUFFER.setdefault(tenant, [])
    buf.append(rec)
    prune(tenant, now_ts=now_ts)
    return len(buf)

def status(tenant: str | None = None) -> dict:
    tenants = [tenant] if tenant else list(TEMPORAL_BUFFER.keys()) or ["global"]
    out = {}
    for t in tenants:
        buf = TEMPORAL_BUFFER.get(t, [])
        prune(t)
        out[t] = {
            "size": len(buf),
            "capacity": TEMPORAL_BUFFER_MAX,
            "retention_s": TEMPORAL_BUFFER_RETENTION_S,
            "ready": len(buf) >= TEMPORAL_BUFFER_READINESS_THRESHOLD,
        }
    return {"tenants": out}

__all__ = [
    "TEMPORAL_BUFFER",
    "TEMPORAL_BUFFER_MAX",
    "TEMPORAL_BUFFER_READINESS_THRESHOLD",
    "TEMPORAL_BUFFER_RETENTION_S",
    "prune",
    "ingest",
    "status",
]
