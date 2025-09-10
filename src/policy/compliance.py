"""Compliance scoring engine (Batch 19).

Computes a composited compliance score based on:
 - Coverage fulfillment vs policy.min_coverage_by_class
 - Required technique presence (minus active exceptions)
 - Adjustment range adherence for configured runtime params
 - Drift / governance stability proxy (uses rolling SNN unique ratio if available)

Score formula (initial heuristic):
  score = 0.4*coverage_component + 0.3*requirements_component + 0.2*adjust_component + 0.1*stability_component
Each component normalized to 0..1.
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import time, hmac, hashlib, json, os
from pathlib import Path

try:
    from policy.dsl import active_exceptions  # type: ignore
except Exception:  # pragma: no cover
    def active_exceptions(policy, now=None):
        return []  # type: ignore

try:
    from coverage.attack_matrix import coverage_summary  # type: ignore
except Exception:  # pragma: no cover
    def coverage_summary():
        return {}

try:
    from config import runtime_params  # type: ignore
except Exception:  # pragma: no cover
    runtime_params = None  # type: ignore

try:
    from core import metrics  # type: ignore
except Exception:  # pragma: no cover
    metrics = None  # type: ignore

_SNAPSHOT_FILE = Path("artifacts/policy_snapshot.json")
_AUDIT_CHAIN_FILE = Path("audit/POLICY_SNAPSHOT_CHAIN.jsonl")


def _coverage_component(policy: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    data = coverage_summary() or {}
    min_by_class = policy.get("min_coverage_by_class", {}) or {}
    class_scores = {}
    accum = 0.0
    total = 0
    for klass, required in min_by_class.items():
        val = float(data.get("by_class", {}).get(klass, 0.0))
        # each class contribution: min( val / required, 1 )
        if required <= 0:
            continue
        contrib = min(val / required, 1.0)
        class_scores[klass] = round(contrib, 4)
        accum += contrib
        total += 1
    comp = accum / total if total else 1.0  # if no requirements, component perfect
    return comp, {"class_scores": class_scores}


def _requirements_component(policy: Dict[str, Any], now: float) -> Tuple[float, Dict[str, Any]]:
    req = set(policy.get("required_techniques", []) or [])
    if not req:
        return 1.0, {"missing": []}
    # active exceptions remove requirement pressure
    ex = active_exceptions(policy, now)
    exempt = {e.get("technique") for e in ex if e.get("technique")}
    effective_req = req - exempt
    data = coverage_summary() or {}
    covered = set(data.get("techniques", []) or [])
    missing = list(sorted(effective_req - covered))
    comp = 1.0 - (len(missing) / max(1, len(effective_req))) if effective_req else 1.0
    return comp, {"missing": missing, "exempt": sorted(exempt)}


def _adjust_component(policy: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    ranges = policy.get("allowed_adjust_range", {}) or {}
    if not ranges or runtime_params is None:
        return 1.0, {"violations": []}
    violations = []
    for key, bounds in ranges.items():
        try:
            val = float(runtime_params.get_param(key) or 0.0)
        except Exception:
            continue
        if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            continue
        lo, hi = float(bounds[0]), float(bounds[1])
        if val < lo - 1e-9 or val > hi + 1e-9:
            violations.append({"param": key, "value": val, "allowed": [lo, hi]})
    comp = 1.0 - (len(violations) / max(1, len(ranges)))
    return comp, {"violations": violations}


def _stability_component() -> Tuple[float, Dict[str, Any]]:
    if metrics is None:
        return 0.5, {"reason": "metrics_unavailable"}
    gauge = getattr(metrics, 'FUSION_SNN_UNIQUE_RATIO_ROLLING', None)
    if gauge is None:
        return 0.5, {"reason": "gauge_missing"}
    try:
        vals = []
        for _k, child in gauge._metrics.items():  # type: ignore[attr-defined]
            vals.append(float(child._value.get()))  # type: ignore[attr-defined]
        if not vals:
            return 0.5, {"reason": "no_values"}
        # Stability heuristic: prefer mid-range (avoid extreme uniqueness which may indicate drift)
        # Score penalizes distance from 0.5 mid-point.
        scores = [1.0 - min(abs(v - 0.5) / 0.5, 1.0) for v in vals]
        return sum(scores) / len(scores), {"values": vals}
    except Exception:
        return 0.5, {"reason": "exception"}


def compute_score(policy: Dict[str, Any]) -> Dict[str, Any]:
    now = time.time()
    cov_c, cov_meta = _coverage_component(policy)
    req_c, req_meta = _requirements_component(policy, now)
    adj_c, adj_meta = _adjust_component(policy)
    stab_c, stab_meta = _stability_component()
    score = 0.4*cov_c + 0.3*req_c + 0.2*adj_c + 0.1*stab_c
    return {
        "timestamp": now,
        "policy_id": policy.get("id"),
        "components": {
            "coverage": cov_c,
            "requirements": req_c,
            "adjustments": adj_c,
            "stability": stab_c,
        },
        "score": round(score, 4),
        "meta": {
            "coverage": cov_meta,
            "requirements": req_meta,
            "adjustments": adj_meta,
            "stability": stab_meta,
        },
    }


def sign_snapshot(obj: Dict[str, Any], secret: str | None = None) -> Dict[str, Any]:
    secret = secret or os.getenv("POLICY_SIGNING_SECRET", "dev-secret")
    payload = json.dumps(obj, sort_keys=True).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return {"object": obj, "signature": sig, "alg": "HMAC-SHA256"}


def write_snapshot(signed: Dict[str, Any]) -> str:
    _SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SNAPSHOT_FILE.write_text(json.dumps(signed, indent=2), encoding="utf-8")
    # Append audit chain entry (immutable hash chain)
    try:
        _AUDIT_CHAIN_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = signed.get("object") or {}
        snap_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        prev_hash = None
        if _AUDIT_CHAIN_FILE.exists():
            try:
                # Read last line efficiently
                with open(_AUDIT_CHAIN_FILE, 'rb') as fh:
                    fh.seek(0, 2)
                    size = fh.tell()
                    block = 1024
                    data = b''
                    while size > 0 and b'\n' not in data:
                        read_size = block if size >= block else size
                        size -= read_size
                        fh.seek(size)
                        data = fh.read(read_size) + data
                    last_line = data.splitlines()[-1] if data else b''
                if last_line:
                    import json as _json
                    prev_hash = _json.loads(last_line.decode('utf-8')).get('chain_hash')
            except Exception:
                prev_hash = None
        chain_material = (prev_hash or '') + snap_hash
        chain_hash = hashlib.sha256(chain_material.encode('utf-8')).hexdigest()
        record = {
            "timestamp": time.time(),
            "policy_id": payload.get("policy_id"),
            "snapshot_hash": snap_hash,
            "prev_chain_hash": prev_hash,
            "chain_hash": chain_hash,
        }
        with _AUDIT_CHAIN_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    except Exception:
        pass
    return str(_SNAPSHOT_FILE)

__all__ = [
    "compute_score",
    "sign_snapshot",
    "write_snapshot",
]
