"""Response Recommendation Engine (Phase 5).

Generates ranked recommended actions for a case using current case state
(confidence, promotion, overdue age, memory artifact count) plus runtime
parameter weighting factors.

Deterministic Ranking:
- Composite score = w_conf * confidence + w_overdue * overdue_factor + w_prom * promoted_flag
- overdue_factor = min(1.0, max(0, overdue_seconds) / max_overdue_norm)
- max_overdue_norm = 3600 by default (1h scaling) unless SLA window differs; kept constant for determinism.

Actions Considered:
1. escalate_ticket
2. quarantine_asset
3. request_memory_acquisition

Eligibility Rules:
- quarantine_asset requires confidence >= response.quarantine.min_confidence
- request_memory_acquisition only if memory_artifacts < response.memory.min_artifacts_for_skip
- escalate_ticket requires confidence >= response.ticket.min_confidence

Playbook Preview:
Returns list of planned actions with stable synthetic IDs (sha256 of case_id+action+version) and rationale strings.
Dry-run only: no side-effects; actual execution pathway reserved for future toggle when dry_run_only disabled.
"""
from __future__ import annotations
import hashlib, time, os, json
from typing import List, Dict, Any
from config import runtime_params
from core import metrics

MAX_OVERDUE_NORM = 3600.0


def _hash_id(case_id: str, action: str, version: str = "v1") -> str:
    h = hashlib.sha256(f"{case_id}:{action}:{version}".encode()).hexdigest()
    return h[:16]


def build_recommendations(case: dict) -> List[Dict[str, Any]]:
    if not runtime_params.get_param("response.recommend.enable"):
        return []
    # Weights
    w_conf = float(runtime_params.get_param("response.weight.confidence") or 0.5)
    w_over = float(runtime_params.get_param("response.weight.overdue_age") or 0.3)
    w_prom = float(runtime_params.get_param("response.weight.promotion") or 0.2)
    conf = float(case.get("last_confidence", 0.0))
    promoted = 1.0 if case.get("promoted") else 0.0
    created_ts = case.get("created_ts") or time.time()
    sla_seconds = 3600  # fallback
    try:
        from core.main import _CASE_SLA_SECONDS  # type: ignore
        sla_seconds = _CASE_SLA_SECONDS
    except Exception:
        pass
    age = time.time() - created_ts
    overdue_seconds = max(0.0, age - sla_seconds)
    overdue_factor = min(1.0, overdue_seconds / MAX_OVERDUE_NORM)
    mem_artifacts = len(case.get("memory_artifact_ids") or [])
    # Thresholds
    min_quarantine = float(runtime_params.get_param("response.quarantine.min_confidence") or 0.8)
    min_ticket = float(runtime_params.get_param("response.ticket.min_confidence") or 0.6)
    skip_mem_artifacts = int(runtime_params.get_param("response.memory.min_artifacts_for_skip") or 2)

    base_components = {
        "confidence": conf,
        "overdue_factor": overdue_factor,
        "promoted": promoted,
        "weights": {"w_conf": w_conf, "w_overdue": w_over, "w_promotion": w_prom},
    }

    actions: List[Dict[str, Any]] = []

    # Escalate Ticket
    if conf >= min_ticket:
        score = w_conf * conf + w_over * overdue_factor + w_prom * promoted
        actions.append({
            "action": "escalate_ticket",
            "score": round(score, 6),
            "components": base_components,
            "rationale": f"confidence={conf:.2f} promoted={bool(promoted)} overdue_factor={overdue_factor:.2f}",
        })
    # Quarantine Asset
    if conf >= min_quarantine:
        score = w_conf * conf + (w_prom * promoted)  # quarantine de-emphasizes overdue
        actions.append({
            "action": "quarantine_asset",
            "score": round(score, 6),
            "components": base_components,
            "rationale": f"confidence={conf:.2f} promoted={bool(promoted)}",
        })
    # Request Memory Acquisition
    if mem_artifacts < skip_mem_artifacts:
        score = w_over * (1.0 - overdue_factor) + (0.15 * (1 - conf))  # encourage early acquisition before high confidence
        actions.append({
            "action": "request_memory_acquisition",
            "score": round(score, 6),
            "components": {**base_components, "memory_artifacts": mem_artifacts},
            "rationale": f"memory_artifacts={mem_artifacts} confidence={conf:.2f}",
        })
    # Sort descending by score (deterministic tie-breaker by action name)
    actions.sort(key=lambda a: (-a["score"], a["action"]))

    for a in actions:
        try:
            metrics.RESPONSE_ACTION_SCORE.observe(a["score"])  # type: ignore[attr-defined]
        except Exception:
            pass
    return actions


def playbook_preview(case: dict) -> Dict[str, Any]:
    recs = build_recommendations(case)
    plan = []
    for r in recs:
        plan.append({
            "id": _hash_id(case["id"], r["action"]),
            "action": r["action"],
            "score": r["score"],
            "dry_run": True,
            "rationale": r["rationale"],
        })
    return {"case_id": case.get("id"), "actions": plan, "count": len(plan)}


def eligible_for_auto_escalation(case: dict, composite: float | None) -> bool:
    if not bool(runtime_params.get_param("response.auto.escalate.enabled")):
        return False
    min_conf = float(runtime_params.get_param("response.auto.escalate.min_confidence") or 0.65)
    require_promoted = bool(runtime_params.get_param("response.auto.escalate.require_promoted"))
    gov_low = float(runtime_params.get_param("response.auto.escalate.gov_low") or 0.25)
    gov_high = float(runtime_params.get_param("response.auto.escalate.gov_high") or 0.9)
    created_ts = case.get("created_ts") or time.time()
    sla_seconds = 3600
    try:
        from core.main import _CASE_SLA_SECONDS  # type: ignore
        sla_seconds = _CASE_SLA_SECONDS
    except Exception:
        pass
    age = time.time() - created_ts
    overdue_s = max(0.0, age - sla_seconds)
    min_overdue = int(runtime_params.get_param("response.auto.escalate.min_overdue_s") or 300)
    # Governance composite guard
    if composite is not None and (composite < gov_low or composite > gov_high):
        return False
    if case.get("last_confidence", 0.0) < min_conf:
        return False
    if require_promoted and not case.get("promoted"):
        return False
    if overdue_s < min_overdue:
        return False
    return True


def build_auto_escalation_decision(case: dict, composite: float | None) -> dict | None:
    if not eligible_for_auto_escalation(case, composite):
        return None
    # Use top recommendation that is not memory acquisition (prefer ticket or quarantine)
    recs = build_recommendations(case)
    chosen = None
    for r in recs:
        if r["action"] != "request_memory_acquisition":
            chosen = r
            break
    if not chosen and recs:
        chosen = recs[0]
    if not chosen:
        return None
    decision = {
        "case_id": case.get("id"),
        "selected_action": chosen["action"],
        "score": chosen["score"],
        "ts": time.time(),
        "auto": True,
    }
    return decision
