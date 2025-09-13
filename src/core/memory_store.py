"""Memory patterns store and helpers extracted from core.main.

Provides in-memory pattern storage with TTL and simple matching logic.
"""
from __future__ import annotations
import time
from typing import List, Dict

try:
    from core import metrics  # type: ignore
except Exception:  # pragma: no cover
    metrics = None  # type: ignore

MEMORY_PATTERNS: List[dict] = []  # {'id','pattern','tags','added_ts','ttl_s'}
MEMORY_PATTERNS_MAX = 5000
MEMORY_PATTERN_DEFAULT_TTL = 0
MEMORY_PATTERN_PRUNE_INTERVAL = 30.0

_LAST_PRUNE_TS = 0.0

def prune(now: float | None = None, force: bool = False) -> int:
    global _LAST_PRUNE_TS, MEMORY_PATTERNS
    now_ts = now or time.time()
    if not force and (now_ts - _LAST_PRUNE_TS) < 5:
        try:
            if hasattr(metrics, 'MEMORY_PATTERN_PRUNE_STALENESS_SECONDS'):
                metrics.MEMORY_PATTERN_PRUNE_STALENESS_SECONDS.set(now_ts - _LAST_PRUNE_TS if _LAST_PRUNE_TS else 0.0)  # type: ignore[attr-defined]
        except Exception:
            pass
        return 0
    _LAST_PRUNE_TS = now_ts
    removed = 0
    kept: List[dict] = []
    for rec in MEMORY_PATTERNS:
        ttl = rec.get("ttl_s") or 0
        if ttl and (rec.get("added_ts", 0) + ttl) < now_ts:
            try: metrics.MEMORY_PATTERN_EVICTIONS_TOTAL.labels(reason="ttl").inc()  # type: ignore[attr-defined]
            except Exception: pass
            removed += 1
            continue
        kept.append(rec)
    MEMORY_PATTERNS = kept[-MEMORY_PATTERNS_MAX:]
    if len(MEMORY_PATTERNS) > MEMORY_PATTERNS_MAX:
        overflow = len(MEMORY_PATTERNS) - MEMORY_PATTERNS_MAX
        try: metrics.MEMORY_PATTERN_EVICTIONS_TOTAL.labels(reason="capacity").inc(overflow)  # type: ignore[attr-defined]
        except Exception: pass
        MEMORY_PATTERNS = MEMORY_PATTERNS[-MEMORY_PATTERNS_MAX:]
    try:
        if hasattr(metrics, 'MEMORY_PATTERN_PRUNE_STALENESS_SECONDS'):
            metrics.MEMORY_PATTERN_PRUNE_STALENESS_SECONDS.set(0.0)  # type: ignore[attr-defined]
    except Exception:
        pass
    return removed

def add_pattern(pattern: str, tags: list[str] | None = None, ttl_s: int | None = None) -> dict:
    import uuid
    tags = tags or []
    ttl = int(ttl_s or MEMORY_PATTERN_DEFAULT_TTL)
    now_ts = time.time()
    rec = {"id": uuid.uuid4().hex[:12], "pattern": pattern, "tags": tags, "ttl_s": ttl, "added_ts": now_ts}
    MEMORY_PATTERNS.append(rec)
    prune(now=now_ts, force=True)
    try:
        if hasattr(metrics, 'MEMORY_PATTERN_TOTAL'):
            metrics.MEMORY_PATTERN_TOTAL.inc()  # type: ignore[attr-defined]
    except Exception:
        pass
    return rec

def list_patterns(q: str | None = None, limit: int = 50) -> list[dict]:
    prune()
    items = list(reversed(MEMORY_PATTERNS))
    if q:
        ql = q.lower()
        items = [r for r in items if ql in (r.get("pattern", "").lower())]
    return items[:limit]

def stats() -> dict:
    last_ts = MEMORY_PATTERNS[-1].get("added_ts") if MEMORY_PATTERNS else None
    usage = {}
    try:
        if hasattr(metrics, 'MEMORY_PATTERN_TOTAL'):
            usage['pattern_total'] = len(MEMORY_PATTERNS)
    except Exception:
        pass
    return {"count": len(MEMORY_PATTERNS), "last_added_ts": last_ts, "usage": usage, "max": MEMORY_PATTERNS_MAX}

def match(blob: str) -> dict:
    if not isinstance(blob, str):
        return {"matched": [], "count": 0}
    lower_blob = blob.lower()
    matched: list[str] = []
    for rec in MEMORY_PATTERNS:
        pat = rec.get("pattern") or ""
        try:
            if pat and pat.lower() in lower_blob:
                matched.append(rec["id"])
        except Exception:
            continue
    try:
        if hasattr(metrics, 'MEMORY_PATTERN_MATCH_TOTAL'):
            metrics.MEMORY_PATTERN_MATCH_TOTAL.labels(outcome="success").inc()  # type: ignore[attr-defined]
    except Exception:
        pass
    return {"matched": matched, "count": len(matched)}

def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0

def correlate_artifacts(a: str, b: str) -> dict:
    import re
    if not isinstance(a, str) or not isinstance(b, str):
        return {"error": "invalid_payload"}
    try:
        toks_a = {t for t in re.split(r"\W+", a.lower()) if t}
        toks_b = {t for t in re.split(r"\W+", b.lower()) if t}
    except Exception:
        toks_a, toks_b = set(), set()
    score = jaccard(toks_a, toks_b)
    if score >= 0.66:
        outcome = "high"
    elif score >= 0.33:
        outcome = "medium"
    else:
        outcome = "low"
    try:
        if hasattr(metrics, 'MEMORY_ARTIFACT_CORRELATION_TOTAL'):
            metrics.MEMORY_ARTIFACT_CORRELATION_TOTAL.labels(outcome=outcome).inc()  # type: ignore[attr-defined]
    except Exception:
        pass
    return {"score": round(score, 4), "outcome": outcome}

__all__ = [
    'MEMORY_PATTERNS',
    'MEMORY_PATTERNS_MAX',
    'MEMORY_PATTERN_DEFAULT_TTL',
    'MEMORY_PATTERN_PRUNE_INTERVAL',
    'prune',
    'add_pattern',
    'list_patterns',
    'stats',
    'match',
    'correlate_artifacts',
]
