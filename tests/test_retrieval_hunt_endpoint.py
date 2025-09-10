import os, time
from fastapi.testclient import TestClient
from core.main import app
from config import runtime_params

client = TestClient(app)

PREDICT_KEY_ENV = "PREDICT_API_KEY"

def _headers():
    return {"x-api-key": os.environ.get(PREDICT_KEY_ENV, "test-predict-key")}

def setup_module(module):  # noqa: D401
    os.environ[PREDICT_KEY_ENV] = "test-predict-key"
    try:
        runtime_params.update_param("retrieval.pipeline.enabled", 1, reason="hunt_test", actor="test")
    except Exception:
        pass


def test_hunt_validation():
    r = client.post("/retrieval/hunt", json={}, headers=_headers())
    assert r.status_code == 200  # empty include allowed -> returns empty list
    r2 = client.post("/retrieval/hunt", json={"include": "not-a-list"}, headers=_headers())
    assert r2.status_code == 400


def test_hunt_basic_flow():
    # Seed a retrieval to persist chunks
    client.post("/retrieval/pipeline", json={"query": "governance signal", "k": 2}, headers=_headers())
    r = client.post("/retrieval/hunt", json={"include": ["governance"], "k": 5}, headers=_headers())
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert data["count"] == len(data["items"])


def test_hunt_time_filter():
    now = time.time()
    # Use since_ts in future to filter everything out
    r = client.post("/retrieval/hunt", json={"include": ["governance"], "since_ts": now + 3600}, headers=_headers())
    assert r.status_code == 200
    assert r.json()["count"] == 0
