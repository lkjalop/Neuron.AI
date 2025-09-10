"""Shadow governance recommendation engine (Batch 5.1).

Generates non-mutating recommendations based on current observed metrics /
internal rolling state. Emissions are stored in an in-memory ring buffer and
optionally persisted to JSONL if runtime param `governance.shadow.persist` is true.

Recommendations are *advisory only*; no runtime param mutation happens here.
"""
from __future__ import annotations

import threading, time, json, os, typing as t, pathlib
from dataclasses import dataclass

try:
    from core import metrics  # type: ignore
except Exception:  # pragma: no cover
    metrics = None  # type: ignore

try:
    from config import runtime_params  # type: ignore
except Exception:  # pragma: no cover
    runtime_params = None  # type: ignore

_MAX_BUFFER = 200  # global cap
_PERSIST_PATH = pathlib.Path("artifacts/governance/shadow_recommendations.jsonl")
_LOCK = threading.Lock()
_BUFFER: list[dict[str, t.Any]] = []
_LAST_PER_TENANT: dict[str, dict[str, t.Any]] = {}

@dataclass
class ShadowContext:
    suppression_rate: float | None = None
    temporal_unique_ratio: float | None = None
    overlap_ratio: float | None = None
    temporal_uplift_ratio: float | None = None  # temporal_applied / baseline

# Heuristic thresholds (could be future runtime params)
_SUPPRESSION_HIGH = 0.85
_TEMPORAL_UPLIFT_MIN = 0.5  # below => consider increase temporal weight
_SUPPRESSION_MID = 0.70
_OVERLAP_LOW = 0.25

_DEF_ACTIONS = {
    "increase_temporal_weight": "temporal_weight_low",
    "decrease_temporal_weight": "temporal_weight_high",
    "raise_suppression_threshold": "sustained_high_suppression",
}


def _persist(rec: dict[str, t.Any]):  # pragma: no cover - IO best-effort
    if not runtime_params:
        return
    try:
        if not bool(runtime_params.get_param("governance.shadow.persist")):
            return
    except Exception:
        return
    try:
        _PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _PERSIST_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")
    except Exception:
        pass


def _emit(rec: dict[str, t.Any]):
    """Insert recommendation into ring buffer & metrics/audit."""
    from config.runtime_params import audit_agent_decision  # local import to avoid cycle
    with _LOCK:
        _BUFFER.append(rec)
        if len(_BUFFER) > _MAX_BUFFER:
            _BUFFER.pop(0)
        tenant = rec.get("tenant") or "unknown"
        _LAST_PER_TENANT[tenant] = rec
        # Update utilization gauge
        try:
            if metrics and getattr(metrics, 'GOVERNANCE_SHADOW_BUFFER_UTILIZATION', None):
                metrics.GOVERNANCE_SHADOW_BUFFER_UTILIZATION.set(len(_BUFFER)/_MAX_BUFFER)  # type: ignore[attr-defined]
        except Exception:
            pass
    # Metrics counter
    try:
        if metrics and getattr(metrics, 'GOVERNANCE_SHADOW_RECOMMENDATIONS_TOTAL', None):
            metrics.GOVERNANCE_SHADOW_RECOMMENDATIONS_TOTAL.labels(tenant=tenant, action=rec.get("action","?")).inc()  # type: ignore[attr-defined]
    except Exception:
        pass
    # Audit chain
    try:
        audit_agent_decision(agent="shadow", action=rec.get("action","?"), detail=rec)
    except Exception:
        pass
    _persist(rec)


def evaluate(tenant: str, ctx: ShadowContext) -> list[dict[str, t.Any]]:
    """Evaluate shadow recommendations for a tenant.

    Returns list of zero or more emitted recommendation records (already stored).
    De-duplicates identical consecutive action for same tenant.
    """
    recs: list[dict[str, t.Any]] = []
    try:
        if not runtime_params or not bool(runtime_params.get_param("governance.shadow.enabled")):
            return recs
    except Exception:
        return recs
    # Basic guards: need at least one signal to evaluate
    if (
        ctx.suppression_rate is None and ctx.temporal_unique_ratio is None and
        ctx.overlap_ratio is None and ctx.temporal_uplift_ratio is None
    ):
        return recs
    # Build candidate actions
    candidates: list[tuple[str, str]] = []  # (action, reason_code)
    # Increase temporal weight if uplift below min AND suppression not already extreme
    if ctx.temporal_uplift_ratio is not None and ctx.temporal_uplift_ratio < _TEMPORAL_UPLIFT_MIN:
        candidates.append(("increase_temporal_weight", _DEF_ACTIONS["increase_temporal_weight"]))
    # Decrease temporal weight if suppression high and overlap low (temporal may be overpowering)
    if (
        ctx.suppression_rate is not None and ctx.suppression_rate >= _SUPPRESSION_HIGH and
        (ctx.overlap_ratio is not None and ctx.overlap_ratio < _OVERLAP_LOW)
    ):
        candidates.append(("decrease_temporal_weight", _DEF_ACTIONS["decrease_temporal_weight"]))
    # Raise suppression threshold if sustained high suppression even with moderate overlap
    if (
        ctx.suppression_rate is not None and ctx.suppression_rate >= _SUPPRESSION_MID and
        (ctx.overlap_ratio is not None and ctx.overlap_ratio < 0.6)
    ):
        candidates.append(("raise_suppression_threshold", _DEF_ACTIONS["raise_suppression_threshold"]))

    emitted = []
    for action, reason_code in candidates:
        now = time.time()
        rec: dict[str, t.Any] = {
            "ts": now,
            "tenant": tenant,
            "action": action,
            "reason_code": reason_code,
            "signals": {
                "suppression_rate": ctx.suppression_rate,
                "temporal_unique_ratio": ctx.temporal_unique_ratio,
                "overlap_ratio": ctx.overlap_ratio,
                "temporal_uplift_ratio": ctx.temporal_uplift_ratio,
            },
        }
        # De-dupe identical consecutive
        last = _LAST_PER_TENANT.get(tenant)
        if last and last.get("action") == action and last.get("reason_code") == reason_code:
            continue
        _emit(rec)
        recs.append(rec)
        emitted.append(action)
    return recs


def list_buffer(limit: int | None = None) -> list[dict[str, t.Any]]:
    with _LOCK:
        data = list(_BUFFER)
    if limit is not None:
        return data[-limit:]
    return data


def latest_for_tenant(tenant: str) -> dict[str, t.Any] | None:
    return _LAST_PER_TENANT.get(tenant)

__all__ = [
    'ShadowContext',
    'evaluate',
    'list_buffer',
    'latest_for_tenant',
]
