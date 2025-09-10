from fastapi.testclient import TestClient
from core.main import app, register_planner, require_api_key
from core.agents.base import registry, AgentBase, AgentContext
import os

class EchoAgent(AgentBase):
    role = 'echo'
    def __init__(self):
        super().__init__('echo')
    def step(self, ctx: AgentContext):
        ctx['echo'] = True
        return {'agent': self.name, 'role': self.role, 'echoed': True}

def test_agents_run_once_endpoint(monkeypatch):
    monkeypatch.setenv('ADMIN_API_KEY', 'test-key')
    registry().register(EchoAgent())
    client = TestClient(app)
    resp = client.post('/agents/run_once', headers={'x-api-key': 'test-key'})
    assert resp.status_code == 200
    data = resp.json()
    assert 'agents' in data and any(r.get('agent') == 'echo' for r in data['agents'])


def test_agents_run_once_unauthorized(monkeypatch):
    monkeypatch.delenv('ADMIN_API_KEY', raising=False)
    client = TestClient(app)
    resp = client.post('/agents/run_once')
    assert resp.status_code in {401,503}  # depends if key required
