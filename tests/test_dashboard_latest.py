import pytest, time, json
from fastapi.testclient import TestClient
from core.main import app

@pytest.fixture
def client(monkeypatch):
    # Provide predict API key for auth dependency
    monkeypatch.setenv('PREDICT_API_KEY', 'testkey')
    return TestClient(app)

class FakeDB:
    def __init__(self):
        self.rows = []
        self.exec_calls = []
    async def fetch(self, sql, *args):  # type: ignore
        if 'FROM dashboard_cache' in sql and self.rows:
            return self.rows
        return []
    async def execute(self, sql, *args):  # type: ignore
        self.exec_calls.append((sql, args))
        return 'OK'

@pytest.mark.asyncio
async def test_dashboard_fresh_recompute(monkeypatch, client):
    # Force compute path (no cache rows)
    fake_db = FakeDB()
    # Monkeypatch storage.postgres.fetch/execute
    import types
    from storage import postgres
    monkeypatch.setattr(postgres, 'fetch', fake_db.fetch)
    monkeypatch.setattr(postgres, 'execute', fake_db.execute)

    # Monkeypatch _dash_compute used inside endpoint
    called = {}
    async def fake_compute():
        called['ran'] = True
        return {'generated_ts': time.time(), 'vulnerability_severity': {}, 'vulnerability_exploit_available': {}, 'open_findings_severity': {}, 'new_findings_7d':0,'closed_findings_7d':0}
    monkeypatch.setattr('core.main._dash_compute', fake_compute)

    r = client.get('/dashboard/latest', headers={'x-api-key':'testkey'})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['cached'] is False
    assert called.get('ran')

@pytest.mark.asyncio
async def test_dashboard_cached_not_stale(monkeypatch, client):
    fake_db = FakeDB()
    now = time.time()
    snap = {'generated_ts': now, 'vulnerability_severity': {'CRITICAL':1}, 'vulnerability_exploit_available': {}, 'open_findings_severity': {}, 'new_findings_7d':0,'closed_findings_7d':0}
    fake_db.rows = [(now, json.dumps(snap))]
    from storage import postgres
    monkeypatch.setattr(postgres, 'fetch', fake_db.fetch)
    monkeypatch.setattr(postgres, 'execute', fake_db.execute)
    # compute should NOT run because not stale
    async def fake_compute():
        raise AssertionError('compute should not run when cache fresh')
    monkeypatch.setattr('core.main._dash_compute', fake_compute)

    r = client.get('/dashboard/latest', headers={'x-api-key':'testkey'})
    assert r.status_code == 200
    data = r.json()
    assert data['cached'] is True
    assert data['stale'] is False
    assert data['vulnerability_severity'] == {'CRITICAL':1}

@pytest.mark.asyncio
async def test_dashboard_cached_stale_refresh(monkeypatch, client):
    fake_db = FakeDB()
    past = time.time() - 1000  # older than small max_age
    snap = {'generated_ts': past, 'vulnerability_severity': {'HIGH':2}, 'vulnerability_exploit_available': {}, 'open_findings_severity': {}, 'new_findings_7d':0,'closed_findings_7d':0}
    fake_db.rows = [(past, json.dumps(snap))]
    from storage import postgres
    monkeypatch.setattr(postgres, 'fetch', fake_db.fetch)
    monkeypatch.setattr(postgres, 'execute', fake_db.execute)
    called = {}
    async def fake_compute():
        called['ran'] = True
        return {'generated_ts': time.time(), 'vulnerability_severity': {'HIGH':3}, 'vulnerability_exploit_available': {}, 'open_findings_severity': {}, 'new_findings_7d':0,'closed_findings_7d':0}
    monkeypatch.setattr('core.main._dash_compute', fake_compute)

    r = client.get('/dashboard/latest?max_age_s=10', headers={'x-api-key':'testkey'})
    assert r.status_code == 200
    data = r.json()
    assert data['cached'] is False  # recomputed path sets cached False
    assert called.get('ran')
