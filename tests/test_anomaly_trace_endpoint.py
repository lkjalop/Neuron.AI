import pytest
import time
from fastapi.testclient import TestClient
from core.main import app
from core.trace_store import traces
from core.event import Event
from core.pipeline import Pipeline
from core import metrics
from config import runtime_params


def _set_admin_env(monkeypatch):
    monkeypatch.setenv('ADMIN_API_KEY', 'secret')
    # Relax HMAC requirement for simpler tests
    monkeypatch.setenv('ADMIN_HMAC_REQUIRED', 'false')


def _inject_trace_records(n=5):
    store = traces()
    store._records.clear()  # type: ignore[attr-defined]
    store._index.clear()    # type: ignore[attr-defined]
    ts = time.time()
    for i in range(n):
        store.add({
            "event_id": f"evt{i}",
            "tenant": "t1",
            "timestamp": ts + i,
            "detectors": [
                {"name": "baseline", "fired": True, "anomalies": [{"score": 5.0, "reason": "baseline_zscore"}]},
                {"name": "snn", "fired": bool(i % 2), "anomalies": ([] if i % 2 == 0 else [{"score": 7.0, "reason": "snn_spike_threshold"}])}
            ],
            "fusion": {"strategy": "baseline_priority", "suppressed": int(i % 2 == 1), "fused_count": 1}
        })


@pytest.mark.asyncio
async def test_recent_trace_listing(monkeypatch):
    _set_admin_env(monkeypatch)
    client = TestClient(app)
    _inject_trace_records(12)
    resp = client.get('/anomalies/trace?limit=5', headers={'x-api-key': 'secret'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['mode'] == 'recent'
    assert data['count'] == 5
    # Ensure ordering is most recent last element of injected subset -> we added increasing timestamps
    returned_ids = [t['event_id'] for t in data['traces']]
    assert returned_ids == [f"evt{i}" for i in range(7,12)][-5:]
    # Each trace should have detectors + fusion keys
    for tr in data['traces']:
        assert 'detectors' in tr and 'fusion' in tr
        assert isinstance(tr['detectors'], list)


@pytest.mark.asyncio
async def test_single_trace_lookup(monkeypatch):
    _set_admin_env(monkeypatch)
    client = TestClient(app)
    _inject_trace_records(3)
    resp = client.get('/anomalies/trace?event_id=evt1', headers={'x-api-key': 'secret'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['mode'] == 'single'
    assert data['trace']['event_id'] == 'evt1'


@pytest.mark.asyncio
async def test_trace_auth_required(monkeypatch):
    _set_admin_env(monkeypatch)
    client = TestClient(app)
    _inject_trace_records(1)
    resp = client.get('/anomalies/trace?limit=1')  # no API key
    assert resp.status_code in (401, 503)  # 503 if key not configured would be alternate path


@pytest.mark.asyncio
async def test_trace_limit_bounds(monkeypatch):
    _set_admin_env(monkeypatch)
    client = TestClient(app)
    _inject_trace_records(2)
    resp = client.get('/anomalies/trace?limit=0', headers={'x-api-key': 'secret'})
    assert resp.status_code == 400
    resp = client.get('/anomalies/trace?limit=600', headers={'x-api-key': 'secret'})
    assert resp.status_code == 400
