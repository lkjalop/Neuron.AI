import os, json
import pytest
from fastapi.testclient import TestClient

# Import app
from core.main import app
from config import runtime_params

client = TestClient(app)

PREDICT_KEY_ENV = "PREDICT_API_KEY"

@pytest.fixture(autouse=True)
def set_predict_key(monkeypatch):
    monkeypatch.setenv(PREDICT_KEY_ENV, "test-predict-key")
    # Ensure flag default enabled for tests unless overridden locally
    try:
        runtime_params.update_param("retrieval.pipeline.enabled", 1, reason="test_setup", actor="test")
    except Exception:
        pass
    yield


def _headers():
    return {"x-api-key": os.environ.get(PREDICT_KEY_ENV, "test-predict-key")}


def test_pipeline_success_basic():
    resp = client.post("/retrieval/pipeline", json={"query": "test query", "k": 3}, headers=_headers())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "trace_id" in data
    assert "plan" in data
    assert "timings" in data
    assert "duration" in data
    assert isinstance(data["plan"], dict)


def test_pipeline_disabled_flag(monkeypatch):
    # Disable via runtime param
    try:
        runtime_params.update_param("retrieval.pipeline.enabled", 0, reason="test_disable", actor="test")
    except Exception:
        pass
    resp = client.post("/retrieval/pipeline", json={"query": "x"}, headers=_headers())
    assert resp.status_code == 503
    assert resp.json().get("detail") == "pipeline_disabled"
    # Re-enable for isolation
    try:
        runtime_params.update_param("retrieval.pipeline.enabled", 1, reason="test_reenable", actor="test")
    except Exception:
        pass


def test_pipeline_validation_errors():
    # Missing query
    r1 = client.post("/retrieval/pipeline", json={}, headers=_headers())
    assert r1.status_code == 400
    # Bad k
    r2 = client.post("/retrieval/pipeline", json={"query": "x", "k": 0}, headers=_headers())
    assert r2.status_code == 400
    r3 = client.post("/retrieval/pipeline", json={"query": "x", "k": 999}, headers=_headers())
    assert r3.status_code == 400


def test_pipeline_unavailable(monkeypatch):
    # Simulate orchestrator absence by monkeypatching imported symbol to None
    from core import main as core_main
    prev = core_main.retrieval_run_pipeline
    core_main.retrieval_run_pipeline = None
    try:
        resp = client.post("/retrieval/pipeline", json={"query": "q"}, headers=_headers())
        assert resp.status_code == 501
    finally:
        core_main.retrieval_run_pipeline = prev
