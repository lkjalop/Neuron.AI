from core.agents.base import registry, AgentBase, AgentContext

class BusAgent(AgentBase):
    role = 'bus'
    def __init__(self):
        super().__init__('bus')
        self.received = []
        registry().subscribe('heartbeat', lambda p: self.received.append(p))
    def step(self, ctx: AgentContext):
        registry().publish('heartbeat', {'ts': 1})
        return {'agent': self.name, 'role': self.role}

def test_message_bus_pub_sub():
    r = registry()
    # Reset state by constructing new agent (registry persists across tests; idempotent)
    agent = BusAgent()
    r.register(agent)
    ctx = AgentContext()
    r.run_once(ctx)
    assert agent.received, 'Expected heartbeat payload received via message bus'
