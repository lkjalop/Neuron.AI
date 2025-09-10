"""Agent base class and registry (multi-agent scaffold)."""
from __future__ import annotations

from typing import Dict, List, Callable, Any
import time


class AgentContext(dict):
    """Shared mutable context passed among agents (light governance later)."""
    pass


class AgentBase:
    """Base class for agents participating in the planner/executive loop."""
    role: str = "base"

    def __init__(self, name: str):
        self.name = name
        self.started = time.time()

    def step(self, ctx: AgentContext) -> dict[str, Any]:  # noqa: D401
        return {"agent": self.name, "role": self.role, "action": "noop"}


class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, AgentBase] = {}
        self._hooks: List[Callable[[AgentBase, dict], None]] = []
        # Simple in-process pub/sub bus: topic -> list[callable(payload)]
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {}

    def register(self, agent: AgentBase):
        if agent.name in self._agents:
            return self._agents[agent.name]
        self._agents[agent.name] = agent
        return agent

    def agents(self) -> List[AgentBase]:
        return list(self._agents.values())

    def add_hook(self, fn: Callable[[AgentBase, dict], None]):
        self._hooks.append(fn)

    def run_once(self, ctx: AgentContext):
        results = []
        for ag in self.agents():
            try:
                res = ag.step(ctx) or {}
            except Exception as e:  # noqa: BLE001
                res = {"error": str(e), "agent": ag.name}
            for h in self._hooks:
                try:
                    h(ag, res)
                except Exception:
                    pass
            results.append(res)
        return results

    # ---- Message Bus API ----
    def publish(self, topic: str, payload: Any):
        subs = list(self._subscribers.get(topic, []))
        for fn in subs:
            try:
                fn(payload)
            except Exception:
                continue

    def subscribe(self, topic: str, handler: Callable[[Any], None]):
        self._subscribers.setdefault(topic, []).append(handler)
        return handler


_REGISTRY: AgentRegistry | None = None


def registry() -> AgentRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = AgentRegistry()
    return _REGISTRY


__all__ = ["AgentBase", "AgentRegistry", "registry", "AgentContext"]
