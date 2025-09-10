"""Agent policy skeleton.

Defines decision types, approval requirements, and a basic in-memory ledger.
Integration with audit chain occurs via runtime_params.audit_agent_decision.
"""
from __future__ import annotations

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Optional
from config.runtime_params import audit_agent_decision


class DecisionType(str, Enum):
    SUMMARIZE = "summarize"
    HUNT_QUERY = "hunt_query"
    PLAYBOOK_SUGGEST = "playbook_suggest"
    LOW_IMPACT_ACTION = "low_impact_action"
    HIGH_IMPACT_ACTION = "high_impact_action"


@dataclass
class PolicyRule:
    decision: DecisionType
    approvals_required: int
    auto_allowed: bool


class PolicyEngine:
    def __init__(self):
        self._rules: Dict[DecisionType, PolicyRule] = {
            DecisionType.SUMMARIZE: PolicyRule(DecisionType.SUMMARIZE, 0, True),
            DecisionType.HUNT_QUERY: PolicyRule(DecisionType.HUNT_QUERY, 0, True),
            DecisionType.PLAYBOOK_SUGGEST: PolicyRule(DecisionType.PLAYBOOK_SUGGEST, 0, True),
            DecisionType.LOW_IMPACT_ACTION: PolicyRule(DecisionType.LOW_IMPACT_ACTION, 1, False),
            DecisionType.HIGH_IMPACT_ACTION: PolicyRule(DecisionType.HIGH_IMPACT_ACTION, 2, False),
        }
        self._approvals: Dict[str, int] = {}
        self._dynamic_suppressed = False

    def _maybe_dynamic_suppress(self):
        """Disable auto allowances dynamically based on coarse anomaly pressure.

        Placeholder heuristic: if more than N pending approvals accumulate, treat environment as high-risk and
        ensure no auto_allowed actions proceed (even if rule says otherwise). Reset condition when queue shrinks.
        """
        pending = sum(1 for k, v in self._approvals.items() if v == 0)
        if pending > 25 and not self._dynamic_suppressed:
            self._dynamic_suppressed = True
            audit_agent_decision("policy", "suppress_auto", {"pending": pending})
        elif pending < 5 and self._dynamic_suppressed:
            self._dynamic_suppressed = False
            audit_agent_decision("policy", "restore_auto", {"pending": pending})

    def evaluate(self, agent: str, decision: DecisionType, detail: Dict[str, Any]) -> Dict[str, Any]:
        self._maybe_dynamic_suppress()
        rule = self._rules[decision]
        decision_id = f"{agent}:{decision}:{hash(str(detail)) & 0xffffffff:x}"
        auto_allowed = rule.auto_allowed and not self._dynamic_suppressed
        approved = auto_allowed and rule.approvals_required == 0
        status = "auto_allowed" if approved else "pending"
        audit_agent_decision(agent, decision.value, {"status": status, "detail": detail, "decision_id": decision_id})
        return {"decision_id": decision_id, "status": status, "approvals_required": rule.approvals_required}

    def approve(self, decision_id: str, approver: str) -> Dict[str, Any]:
        count = self._approvals.get(decision_id, 0) + 1
        self._approvals[decision_id] = count
        # Simplified extraction of required approvals encoded earlier (not persisted; assume 2 for high impact, 1 for low)
        required = 2 if 'HIGH_IMPACT_ACTION' in decision_id.upper() else 1
        status = "approved" if count >= required else "pending"
        audit_agent_decision("approver", "approval", {"decision_id": decision_id, "approver": approver, "count": count, "status": status})
        return {"decision_id": decision_id, "approvals": count, "status": status}


_ENGINE: Optional[PolicyEngine] = None


def policy() -> PolicyEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = PolicyEngine()
    return _ENGINE


__all__ = ["policy", "DecisionType", "PolicyEngine"]
