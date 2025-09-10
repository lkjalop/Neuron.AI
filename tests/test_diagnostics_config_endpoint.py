from fastapi.testclient import TestClient
from src.core.main import app
from config import runtime_params

client = TestClient(app)

def test_diagnostics_config_shape():
    # Seed a couple runtime params and bounds
    try:
        runtime_params.update_param("fusion.weight.temporal.min", 0.1, "test", actor="test")
        runtime_params.update_param("fusion.weight.temporal.max", 0.9, "test", actor="test")
        runtime_params.update_param("test.example.param", 42, "test", actor="test")
    except Exception:
        pass
    r = client.get("/diagnostics/config")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "runtime" in data
    assert "policies" in data
    assert "exceptions" in data
    assert "bounds" in data
    b = data["bounds"]
    if b:
        # If bounds extraction worked, temporal weight should have min/max
        tw = b.get("fusion.weight.temporal")
        if tw:
            assert "min" in tw and "max" in tw

