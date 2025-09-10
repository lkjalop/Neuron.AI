import pytest, asyncio
from fastapi.testclient import TestClient
from core.main import app, pipeline, TENANTS, Pipeline
from config import runtime_params

@pytest.fixture(scope="function")
def test_app():
    # Force deterministic strategy / params before startup
    runtime_params.update_param("detection.fusion.strategy", "weighted_sum", reason="test_setup", actor="test")
    runtime_params.update_param("fusion.weighted_sum.suppress_threshold", 0.50, reason="test_setup", actor="test")
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="function")
def ensure_pipeline():
    # Ensure pipeline is initialized (startup event should have run once under TestClient)
    from core.main import pipeline as p
    assert p is not None
    return p
