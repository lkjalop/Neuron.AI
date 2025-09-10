import os, time, json, asyncio
from fastapi.testclient import TestClient
from core.main import build_app
from config import runtime_params

API_KEY = "testkey123"

def _auth_headers():
    return {"x-api-key": API_KEY}


def setup_module(module):  # noqa: D401
    os.environ["ADMIN_API_KEY"] = API_KEY


def test_inline_and_flush_path(monkeypatch):
    # Ensure inline detection enabled
    runtime_params.update_param("ingest.inline_detection.enabled", True, reason="test")
    # Reduce warmup jitter events for deterministic test
    runtime_params.update_param("baseline.warmup_jitter_events", 0, reason="test")
    test_app = build_app()
    with TestClient(test_app) as client:
        # Send events without inline detect (queued)
        for i in range(5):
            ev = {"tenant_id": "tenantA", "event_id": f"q{i}", "features": {"f1": i * 1.0}}
            r = client.post("/ingest", json=ev)
            assert r.status_code == 200
            assert r.json()["inline"] is False
        # Send events with inline detection header
        for i in range(5):
            ev = {"tenant_id": "tenantA", "event_id": f"i{i}", "features": {"f1": (i+10) * 1.0}}
            r = client.post("/ingest", json=ev, headers={"x-inline-detect": "true"})
            assert r.status_code == 200
            assert r.json()["inline"] is True
        # Flush queued events
        fr = client.post("/admin/flush", headers=_auth_headers())
        assert fr.status_code == 200
        data = fr.json()
        assert "flushed_events" in data
        # After flush, queue should drain; second flush returns 0 or small value
        fr2 = client.post("/admin/flush", headers=_auth_headers())
        assert fr2.status_code == 200
        data2 = fr2.json()
        # Allow at most 1 residual due to in-flight processing; perform final drain
        assert data2["flushed_events"] <= 1
        attempts = 0
        flushed_remaining = data2["flushed_events"]
        while flushed_remaining > 0 and attempts < 3:
            frx = client.post("/admin/flush", headers=_auth_headers())
            assert frx.status_code == 200
            flushed_remaining = frx.json().get("flushed_events", 0)
            attempts += 1
        assert flushed_remaining == 0

        # Basic anomaly endpoint call to ensure system still responds
        ar = client.get("/anomalies", params={"tenant": "tenantA"}, headers=_auth_headers())
        assert ar.status_code == 200
        body = ar.json()
        assert "count" in body
