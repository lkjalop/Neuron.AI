"""Reliability failure recorder and playbook generator.

Captures recent failures (component, error, duration) and periodically writes a
JSON artifact summarizing patterns, counts, and MTTR approximations.
"""
from __future__ import annotations
import time, json, threading
from pathlib import Path
from typing import Dict, Any, List

_MAX_EVENTS = 500
_lock = threading.Lock()
_events: List[Dict[str, Any]] = []
_ARTIFACT = Path("artifacts/reliability_playbook.json")


def record_failure(component: str, error: str, duration_s: float | None = None):
    evt = {
        "ts": time.time(),
        "component": component,
        "error": error[:300],
        "duration_s": duration_s,
    }
    with _lock:
        _events.append(evt)
        if len(_events) > _MAX_EVENTS:
            del _events[0: len(_events) - _MAX_EVENTS]


def snapshot(limit: int = 200) -> List[Dict[str, Any]]:
    with _lock:
        return list(_events[-limit:])


def generate_artifact(window_s: int = 3600) -> Path:
    cutoff = time.time() - window_s
    with _lock:
        recent = [e for e in _events if e["ts"] >= cutoff]
    # Aggregate per component
    agg: Dict[str, Dict[str, Any]] = {}
    for e in recent:
        c = e["component"]
        a = agg.setdefault(c, {"count": 0, "errors": {}, "avg_duration_s": 0.0})
        a["count"] += 1
        if e.get("duration_s"):
            # incremental average
            n = a.get("_dur_n", 0) + 1
            cur_avg = a["avg_duration_s"]
            new_avg = cur_avg + (e["duration_s"] - cur_avg) / n  # type: ignore
            a["avg_duration_s"] = round(new_avg, 3)
            a["_dur_n"] = n
        err_key = e["error"]
        a["errors"][err_key] = a["errors"].get(err_key, 0) + 1
    # Simplify
    for v in agg.values():
        v.pop("_dur_n", None)
    payload = {
        "generated_ts": time.time(),
        "window_s": window_s,
        "components": agg,
        "recent_samples": recent[-50:],
    }
    _ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    _ARTIFACT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return _ARTIFACT

__all__ = ["record_failure", "snapshot", "generate_artifact"]
