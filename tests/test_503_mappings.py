import pytest
from fastapi.testclient import TestClient
from core.main import app

@pytest.fixture(scope="module")
def client():
    import os
    os.environ["ADMIN_API_KEY"] = "adminkey"
    os.environ["PREDICT_API_KEY"] = "predictkey"
    return TestClient(app)

@pytest.mark.asyncio
async def test_sla_upcoming_persistence_error_monkeypatch(client, monkeypatch):
    # Force vuln_store.list_findings to raise to assert 503 mapping
    import core.main as main_mod
    if not getattr(main_mod, 'vuln_store', None):
        pytest.skip("vuln_store not available in this test environment")
    class DummyStore:
        async def list_findings(self, *args, **kwargs):
            raise RuntimeError("boom")
    monkeypatch.setattr(main_mod, 'vuln_store', DummyStore())
    r = client.get('/findings/sla/upcoming', headers={"x-api-key":"predictkey"})
    assert r.status_code == 503
    js = r.json()
    assert js['error']['code'].startswith('list_unavailable') or js['error']['code'] == 'list_unavailable'

@pytest.mark.asyncio
async def test_ticket_batching_persistence_error_monkeypatch(client, monkeypatch):
    import core.main as main_mod
    if not getattr(main_mod, 'vuln_store', None):
        pytest.skip("vuln_store not available in this test environment")
    class DummyStore:
        async def list_findings(self, *args, **kwargs):
            raise RuntimeError("boom2")
    monkeypatch.setattr(main_mod, 'vuln_store', DummyStore())
    r = client.post('/tickets/remediation', json={}, headers={"x-api-key":"predictkey"})
    assert r.status_code == 503
    js = r.json()
    assert 'list_unavailable' in js['error']['code']
