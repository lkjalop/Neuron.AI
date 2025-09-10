import pytest, time
from fastapi.testclient import TestClient
from core.main import app, _record_ingest_event

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('PREDICT_API_KEY', 'testkey')
    return TestClient(app)

class FeedStateStub:
    def __init__(self):
        self.state = {}
    async def get_feed_state(self, name):  # simulate signature
        return self.state.get(name)

@pytest.mark.asyncio
async def test_ingest_status_counters_and_feed(monkeypatch, client):
    # Simulate some events
    for _ in range(3):
        _record_ingest_event('qualys')
    for _ in range(2):
        _record_ingest_event('generic')

    # Monkeypatch get_feed_state used in endpoint
    stub = FeedStateStub()
    now = time.time()
    stub.state['qualys'] = {'last_fetch_ts': now - 100, 'last_status': 'ok'}
    stub.state['tenable'] = {'last_fetch_ts': now - 5000, 'last_status': 'error'}

    # Patch storage.vuln_store.get_feed_state symbol resolution inside endpoint to our stub method
    import types
    async def fake_get_feed_state(name):
        return await stub.get_feed_state(name)
    # When imported in endpoint module path is storage.vuln_store.get_feed_state, so patch there
    import storage.vuln_store as vs
    monkeypatch.setattr(vs, 'get_feed_state', fake_get_feed_state)

    r = client.get('/ingest/status', headers={'x-api-key':'testkey'})
    assert r.status_code == 200
    data = r.json()
    names = {c['name']: c for c in data['connectors']}
    assert 'qualys' in names and names['qualys']['events_24h'] >= 3
    assert 'generic' in names and names['generic']['events_24h'] == 2
    # Qualys fresh (<3600 -> OK)
    assert names['qualys']['status'] == 'OK'
