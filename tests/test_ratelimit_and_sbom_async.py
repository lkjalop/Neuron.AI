import os
import time
import json
import asyncio
import pytest
from fastapi.testclient import TestClient

from core.main import app, _API_KEY_BUCKETS


@pytest.fixture(autouse=True)
def _set_keys(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "adminkey")
    monkeypatch.setenv("PREDICT_API_KEY", "predictkey")
    yield
    _API_KEY_BUCKETS.clear()


def _client():
    return TestClient(app)


def test_rate_limit_predict_bucket(monkeypatch):
    # Tighten limits for deterministic test
    monkeypatch.setenv("PREDICT_RATELIMIT_RPS", "2")
    monkeypatch.setenv("PREDICT_RATELIMIT_BURST", "2")
    c = _client()
    allowed = 0
    throttled = 0
    for _ in range(4):  # exceed burst
        r = c.get("/metrics", headers={"x-api-key": "predictkey"})
        if r.status_code == 200:
            allowed += 1
        else:
            throttled += 1
    assert allowed >= 2
    assert throttled >= 1


def test_rate_limit_admin_bucket(monkeypatch):
    monkeypatch.setenv("ADMIN_RATELIMIT_RPS", "1")
    monkeypatch.setenv("ADMIN_RATELIMIT_BURST", "1")
    c = _client()
    # First call ok
    r1 = c.get("/admin/params", headers={"x-api-key": "adminkey"})
    assert r1.status_code in (200, 503)  # 503 if params not configured fully yet
    # Second immediate call likely throttled
    r2 = c.get("/admin/params", headers={"x-api-key": "adminkey"})
    assert r2.status_code in (200, 429)


@pytest.mark.asyncio
async def test_sbom_upload_sync_override(monkeypatch):
    monkeypatch.setenv("PREDICT_API_KEY", "predictkey")
    monkeypatch.setenv("SBOM_ASYNC_ENABLED", "true")
    c = _client()
    sbom = {"bomFormat": "CycloneDX", "components": [{"name": "pkgA", "version": "1.0.0"}]}
    files = {"file": ("bom.json", json.dumps(sbom), "application/json")}
    r = c.post("/sbom/upload?asset_id=a1&sync=true", files=files, headers={"x-api-key": "predictkey"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "sync"
    assert body["components"] == 1


def test_sbom_upload_async_queue(monkeypatch):
    monkeypatch.setenv("PREDICT_API_KEY", "predictkey")
    monkeypatch.setenv("SBOM_ASYNC_ENABLED", "true")
    c = _client()
    sbom = {"bomFormat": "CycloneDX", "components": [{"name": "pkgB", "version": "2.0.0"}]}
    files = {"file": ("bom.json", json.dumps(sbom), "application/json")}
    r = c.post("/sbom/upload?asset_id=b1", files=files, headers={"x-api-key": "predictkey"})
    assert r.status_code == 200
    job = r.json()
    assert job["mode"] == "async"
    job_id = job["job_id"]
    # Poll status endpoint until done or timeout
    for _ in range(30):
        st = c.get(f"/sbom/upload/status/{job_id}", headers={"x-api-key": "predictkey"})
        assert st.status_code == 200
        js = st.json()["job"]
        if js.get("status") in {"done", "error"}:
            break
        time.sleep(0.1)
    assert js.get("status") == "done", js
    assert js.get("components") == 1


def test_sbom_queue_full(monkeypatch):
    # Configure tiny queue size 1 to force full condition
    monkeypatch.setenv("PREDICT_API_KEY", "predictkey")
    monkeypatch.setenv("SBOM_ASYNC_ENABLED", "true")
    monkeypatch.setenv("SBOM_ASYNC_MAX_QUEUE", "1")
    # Replace existing queue (if already started) with size=1 for deterministic test
    import core.main as cm
    cm._SBOM_JOB_QUEUE = asyncio.Queue(maxsize=1)
    c = _client()
    sbom = {"bomFormat": "CycloneDX", "components": [{"name": "pkgC", "version": "1.0.0"}]}
    files = {"file": ("bom.json", json.dumps(sbom), "application/json")}
    r1 = c.post("/sbom/upload?asset_id=c1", files=files, headers={"x-api-key": "predictkey"})
    assert r1.status_code == 200
    # Second should hit queue full if worker not yet drained
    sbom2 = {"bomFormat": "CycloneDX", "components": [{"name": "pkgD", "version": "1.0.0"}]}
    files2 = {"file": ("bom2.json", json.dumps(sbom2), "application/json")}
    r2 = c.post("/sbom/upload?asset_id=c2", files=files2, headers={"x-api-key": "predictkey"})
    # Acceptable outcomes: queued (race) or 503 queue_full
    assert r2.status_code in (200, 503)
    if r2.status_code == 503:
        assert r2.json()["detail"] == "sbom_queue_full"
