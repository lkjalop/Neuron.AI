"""Fusion weight change auditing stub.

Provides a helper to record weight vector changes for adaptive fusion strategies.
Writes an entry to `audit/AUDIT_LOG.md` and increments Prometheus counter.

Format Example:
  [2025-09-03T12:34:56Z] strategy=adaptive_weights old={'baseline':0.5,'snn':0.5} new={'baseline':0.4,'snn':0.6} reason=drift_compensation delta={'baseline':-0.1,'snn':0.1}
"""
from __future__ import annotations

import json, os, datetime, hashlib
from typing import Dict, Any
from core import metrics

AUDIT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "audit", "AUDIT_LOG.md")


def record_weight_change(strategy: str, old: Dict[str, float], new: Dict[str, float], reason: str):
    try:
        metrics.FUSION_WEIGHT_UPDATES_TOTAL.labels(strategy=strategy).inc()  # type: ignore[attr-defined]
    except Exception:
        pass
    delta = {k: new.get(k, 0.0) - old.get(k, 0.0) for k in set(old) | set(new)}
    line = {
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "strategy": strategy,
        "old": old,
        "new": new,
        "delta": delta,
        "reason": reason,
    }
    try:
        os.makedirs(os.path.dirname(AUDIT_PATH), exist_ok=True)
        with open(AUDIT_PATH, "a", encoding="utf-8") as f:
            f.write(f"WEIGHT_CHANGE {json.dumps(line)}\n")
    except Exception:
        pass

__all__ = ["record_weight_change"]


def record_report_diff(diff: dict):
    """Record a hash of the report diff structure for chain integrity extension.

    Stores a REPORT_DIFF line with sha256 hash and counts of added/removed/changed keys.
    """
    try:
        payload = json.dumps(diff, sort_keys=True)
        h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        line = {
            "ts": datetime.datetime.utcnow().isoformat() + "Z",
            "hash": h,
            "added": len(diff.get("added", {})),
            "removed": len(diff.get("removed", {})),
            "changed": len(diff.get("changed", {})),
        }
        os.makedirs(os.path.dirname(AUDIT_PATH), exist_ok=True)
        with open(AUDIT_PATH, "a", encoding="utf-8") as f:
            f.write(f"REPORT_DIFF {json.dumps(line)}\n")
    except Exception:
        pass

__all__.append("record_report_diff")
