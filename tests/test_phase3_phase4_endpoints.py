import time
import pytest
from fastapi.testclient import TestClient

from core.main import app, runtime_params

def make_client():
    import os
    os.environ["ADMIN_API_KEY"] = "adminkey"
    os.environ["PREDICT_API_KEY"] = "predictkey"
    return TestClient(app)

@pytest.fixture(scope="module")
def client():
    return make_client()

def test_snn_toggle_cycle(client):
    # Ensure starts disabled (best-effort)
    r = client.post("/snn/toggle", json={"enabled": True}, headers={"x-api-key": "adminkey"})
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    # Disable again
    r2 = client.post("/snn/toggle", json={"enabled": False}, headers={"x-api-key": "adminkey"})
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["enabled"] is False

def test_fusion_weights_update(client):
    # Update baseline + snn weights
    r = client.post("/fusion/weights/update", json={"weights": {"baseline": 0.7, "snn": 0.3}}, headers={"x-api-key": "adminkey"})
    assert r.status_code == 200
    js = r.json()
    applied = js.get("applied") or {}
    assert applied.get("baseline") == 0.7
    assert applied.get("snn") == 0.3
    # Bad body
    r_bad = client.post("/fusion/weights/update", json={}, headers={"x-api-key": "adminkey"})
    assert r_bad.status_code == 400

def _ingest_event(client, eid: str, tenant: str = "t1"):
    ev = {"event_id": eid, "tenant_id": tenant, "message": f"event {eid}"}
    r = client.post("/ingest", json=ev)
    assert r.status_code == 200

def test_fusion_decisions_recent(client):
    # Ingest a few events to populate decision buffer (best-effort)
    for i in range(3):
        _ingest_event(client, f"f{i}")
    r = client.get("/fusion/decisions/recent?limit=5", headers={"x-api-key": "adminkey"})
    assert r.status_code == 200
    js = r.json()
    assert "count" in js and isinstance(js.get("items"), list)

def test_governance_signal(client):
    r = client.get("/governance/signal", headers={"x-api-key": "adminkey"})
    assert r.status_code == 200
    js = r.json()
    assert "components" in js
    comps = js.get("components") or {}
    assert "precision_proxy" in comps
    assert "exposure_total" in comps
