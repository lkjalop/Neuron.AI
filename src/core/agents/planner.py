"""Planner agent stub orchestrating strategic adjustments (scaffold)."""
from __future__ import annotations

from core.agents.base import AgentBase, AgentContext, registry
import time
from config import runtime_params


class PlannerAgent(AgentBase):
    role = "planner"

    def __init__(self):
        super().__init__(name="planner")

    def step(self, ctx: AgentContext):  # noqa: D401
        # Example: reflect current temporal enable flag for dashboard consumption
        temporal_enabled = bool(runtime_params.get_param("detection.temporal.enable_transformer"))
        ctx["temporal_enabled"] = temporal_enabled
        # Publish lightweight heartbeat (no more than 1/sec)
        now = time.time()
        last = ctx.get("_planner_last_heartbeat", 0)
        if (now - last) >= 1.0:
            ctx["_planner_last_heartbeat"] = now
            try:
                registry().publish("heartbeat", {
                    "ts": now,
                    "agent": self.name,
                    "uptime_s": round(now - self.started, 3),
                    "temporal_enabled": temporal_enabled,
                })
            except Exception:
                pass
        return {"agent": self.name, "role": self.role, "temporal_enabled": temporal_enabled}


def register_planner():
    registry().register(PlannerAgent())


__all__ = ["PlannerAgent", "register_planner"]
