"""Remediation plan orchestration & signing.

Generates a prioritized remediation plan based on highest path_risk / emergence
findings and allows signing (attestation) which stores immutable record.
"""
from __future__ import annotations

import hashlib, json, time, hmac, os
from typing import List, Dict, Any

from storage import postgres  # type: ignore
from predictive.paths import build_paths  # type: ignore


def _hash_content(content: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


async def generate_plan(limit: int = 20) -> Dict[str, Any]:
    paths = await build_paths(limit=limit)
    # Collapse by asset -> list top findings
    recs: List[Dict[str, Any]] = []
    # Preload SLA & exception info for findings in one query batch
    finding_ids = [p["finding"]["id"] for p in paths]
    sla_map: Dict[str, Any] = {}
    exc_map: Dict[str, bool] = {}
    if finding_ids:
        try:
            rows = await postgres.fetch(
                "SELECT id, sla_due_ts FROM findings WHERE id = ANY($1)", finding_ids
            )
            for r in rows:
                sla_map[r["id"]] = r["sla_due_ts"]
        except Exception:
            pass
        try:
            erows = await postgres.fetch(
                "SELECT finding_id, status FROM exceptions WHERE finding_id = ANY($1) AND status='active'",
                finding_ids,
            )
            for r in erows:
                exc_map[r["finding_id"]] = True
        except Exception:
            pass
    for p in paths:
        finding = p["finding"]
        action = {
            "finding_id": finding["id"],
            "cve_id": finding["cve_id"],
            "suggested_action": "Apply vendor patch / update component",
            "emergence_p": finding.get("emergence_p"),
            "risk_score": finding.get("risk_score"),
            "path_risk": p["path_risk"],
            "sla_due_ts": sla_map.get(finding["id"]),
            "has_active_exception": exc_map.get(finding["id"], False),
        }
        recs.append(action)
    plan = {
        "generated_ts": time.time(),
        "recommendations": recs,
        "count": len(recs),
        "version": 1,
    }
    plan["plan_hash"] = _hash_content(plan)
    return plan


async def sign_plan(plan: Dict[str, Any], signer: str) -> Dict[str, Any]:
    # Validate hash
    provided_hash = plan.get("plan_hash")
    calc_hash = _hash_content({k: v for k, v in plan.items() if k != "plan_hash"})
    if provided_hash != calc_hash:
        raise ValueError("plan_hash_mismatch")
    secret = os.getenv("PLAN_SIGNING_SECRET", "dev-secret")
    signature = hmac.new(secret.encode(), provided_hash.encode(), hashlib.sha256).hexdigest()
    plan_id = f"rplan-{int(time.time()*1000)}"
    await postgres.execute(
        """
        INSERT INTO remediation_plans (id, created_ts, plan_hash, content, signed_by, signature)
        VALUES ($1,$2,$3,$4,$5,$6)
        """,
        plan_id,
        time.time(),
        provided_hash,
        json.dumps(plan),
        signer,
        signature,
    )
    return {"id": plan_id, "signature": signature, "plan_hash": provided_hash}


async def get_plan(plan_id: str) -> Dict[str, Any] | None:
    rows = await postgres.fetch("SELECT id, content, signature, signed_by FROM remediation_plans WHERE id=$1", plan_id)
    if not rows:
        return None
    r = rows[0]
    try:
        content = json.loads(r["content"]) if isinstance(r["content"], str) else r["content"]
    except Exception:
        content = {}
    return {
        "id": r["id"],
        "content": content,
        "signed_by": r["signed_by"],
        "signature": r["signature"],
    }

__all__ = ["generate_plan", "sign_plan", "get_plan"]
