from __future__ import annotations

from core.agents.base import registry, AgentBase, AgentContext
from core.agents.planner import register_planner


class EchoAgent(AgentBase):
    role = "echo"
    def __init__(self):
        super().__init__(name="echo")
    def step(self, ctx: AgentContext):
        ctx["echo"] = True
        return {"agent": self.name, "role": self.role, "echo": True}


def test_agent_registry_basic():
    register_planner()
    registry().register(EchoAgent())
    ctx = AgentContext()
    results = registry().run_once(ctx)
    assert any(r.get("agent") == "planner" for r in results)
    assert any(r.get("agent") == "echo" for r in results)
    assert ctx.get("echo") is True
