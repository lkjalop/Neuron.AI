"""IAM: RBAC + ABAC scaffolding with agent drift hooks.
This is an initial lightweight implementation to be expanded.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Set, Any, Optional, Callable
import time

# ---- Role-Based Access Control (RBAC) ----

@dataclass
class Role:
    name: str
    permissions: Set[str]

@dataclass
class Principal:
    principal_id: str
    roles: Set[str] = field(default_factory=set)
    attributes: Dict[str, Any] = field(default_factory=dict)  # For ABAC
    kind: str = "user"  # or "agent"

class RBAC:
    def __init__(self):
        self.roles: Dict[str, Role] = {}
        self.principals: Dict[str, Principal] = {}

    def define_role(self, name: str, permissions: Set[str]):
        self.roles[name] = Role(name, permissions)

    def assign_role(self, principal_id: str, role: str):
        p = self.principals.setdefault(principal_id, Principal(principal_id))
        p.roles.add(role)

    def check(self, principal_id: str, permission: str) -> bool:
        p = self.principals.get(principal_id)
        if not p:
            return False
        for r in p.roles:
            role = self.roles.get(r)
            if role and permission in role.permissions:
                return True
        return False

# ---- Attribute-Based Access Control (ABAC) ----

PolicyFunc = Callable[[Principal, Dict[str, Any]], bool]

@dataclass
class ABACPolicy:
    name: str
    description: str
    condition: PolicyFunc
    effect: str = "allow"  # or deny

class ABAC:
    def __init__(self):
        self.policies: Dict[str, ABACPolicy] = {}

    def add_policy(self, policy: ABACPolicy):
        self.policies[policy.name] = policy

    def evaluate(self, principal: Principal, context: Dict[str, Any]) -> bool:
        decision = False
        for pol in self.policies.values():
            if pol.condition(principal, context):
                if pol.effect == "deny":
                    return False
                decision = True
        return decision

# ---- Agent Drift Monitoring ----

@dataclass
class AgentDriftRecord:
    agent_id: str
    timestamp: float
    attribute_snapshot: Dict[str, Any]
    anomaly_score: float

class AgentDriftMonitor:
    def __init__(self):
        self.history: Dict[str, list[AgentDriftRecord]] = {}

    def record(self, principal: Principal, anomaly_score: float):
        rec = AgentDriftRecord(
            agent_id=principal.principal_id,
            timestamp=time.time(),
            attribute_snapshot=dict(principal.attributes),
            anomaly_score=anomaly_score,
        )
        self.history.setdefault(principal.principal_id, []).append(rec)

    def recent_anomalies(self, principal_id: str, window_sec: int = 3600) -> int:
        now = time.time()
        recs = self.history.get(principal_id, [])
        return sum(1 for r in recs if now - r.timestamp <= window_sec and r.anomaly_score > 0.8)

# ---- Composite IAM Service ----

class IAMService:
    def __init__(self):
        self.rbac = RBAC()
        self.abac = ABAC()
        self.drift = AgentDriftMonitor()

    def is_allowed(self, principal_id: str, permission: str, context: Optional[Dict[str, Any]] = None) -> bool:
        context = context or {}
        # RBAC coarse gate
        if not self.rbac.check(principal_id, permission):
            return False
        principal = self.rbac.principals.get(principal_id)
        if not principal:
            return False
        # ABAC refinement
        if not self.abac.evaluate(principal, context):
            return False
        # Drift heuristic (deny or flag if anomalous)
        if self.drift.recent_anomalies(principal_id) > 3:
            return False
        return True


# Backward-compatible authorize helper for tests expecting simple API
@dataclass
class AuthzResult:
    allowed: bool
    reason: str = ""

def authorize(subject: dict, action: str, resource_type: str, resource_tenant: str | None = None) -> AuthzResult:  # pragma: no cover - thin wrapper
    """Simplified authorize used in early tests.

    Interprets roles directly from subject dict and applies minimal logic:
    - 'viewer' can read events
    - 'admin' wildcard
    - future expansion hooks with IAMService
    """
    roles = set(subject.get("roles", []))
    if "admin" in roles:
        return AuthzResult(True)
    if action == "read" and resource_type == "event" and "viewer" in roles:
        return AuthzResult(True)
    return AuthzResult(False, "denied")

# Example default roles/policies bootstrapping

def bootstrap_default_iam(iam: IAMService):
    iam.rbac.define_role("admin", {"*"})
    iam.rbac.define_role("analyst", {"events:read", "detections:read"})
    iam.rbac.define_role("responder", {"events:read", "actions:execute"})
    iam.rbac.define_role("agent", {"events:read", "detections:write"})

    # ABAC Policy: tenant isolation
    iam.abac.add_policy(ABACPolicy(
        name="tenant_isolation",
        description="Principal tenant must match resource tenant",
        condition=lambda p, ctx: ctx.get("tenant_id") is None or p.attributes.get("tenant_id") == ctx.get("tenant_id"),
    ))

    # ABAC Policy: agent risk gating example
    iam.abac.add_policy(ABACPolicy(
        name="agent_low_risk",
        description="Agent must have risk_score < 0.7 to write detections",
        condition=lambda p, ctx: (p.kind != "agent") or (p.attributes.get("risk_score", 0) < 0.7),
    ))

