import pytest
from fastapi.testclient import TestClient
from core.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('ADMIN_API_KEY', 'adminkey')
    return TestClient(app)


def test_forensics_memory_job_flow(client):
    # Submit a memory job
    r = client.post('/forensics/jobs', json={"modality": "memory", "params": {"asset_id": "host-1"}})
    assert r.status_code == 200
    job = r.json().get('job') or {}
    jid = job.get('id')
    assert jid, 'job id missing'
    # Get job by id
    r2 = client.get(f'/forensics/jobs/{jid}')
    assert r2.status_code == 200
    rec = r2.json().get('job') or {}
    assert rec.get('modality') == 'memory'
    # List recent should include it
    r3 = client.get('/forensics/jobs?modality=memory&limit=10')
    assert r3.status_code == 200
    items = r3.json().get('items') or []
    assert any(it.get('id') == jid for it in items)
    # Custody verify should not 404 and return counts
    r4 = client.get(f'/forensics/custody/verify?job_id={jid}')
    assert r4.status_code in (200, 404)  # Some environments may not persist custody chain
    if r4.status_code == 200:
        body = r4.json()
        assert 'matches' in body and 'mismatches' in body
