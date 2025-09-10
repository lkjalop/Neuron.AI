import os, time
from fastapi.testclient import TestClient
from core.main import app, _CASES, _create_case  # type: ignore
from config.runtime_params import update_param

client = TestClient(app)

ADMIN_KEY = "adminkey"
os.environ["ADMIN_API_KEY"] = ADMIN_KEY


def _enable_execution():
    update_param("response.execution.enable", True, reason="test")
    update_param("response.action.cooldown_s", 1, reason="test")
    update_param("response.action.max_per_case_per_hour", 5, reason="test")


def test_execution_disabled():
    # Ensure disabled path blocks
    update_param("response.execution.enable", False, reason="test")
    case = _create_case("anom-exec1", tenant="t1")
    r = client.post(f"/response/execute/{case['id']}", json={"action": "ticket"})
    assert r.status_code == 403
    data = r.json()
    # Endpoint may return either structured envelope or raw detail depending on exception handler ordering
    if isinstance(data, dict) and "error" in data:
        assert data["error"]["code"].startswith("execution_disabled") or data["error"]["code"] == "execution_disabled"
    else:
        # raw plain string or dict with detail
        if "detail" in data:
            assert "execution_disabled" in str(data["detail"]).lower()
        else:
            assert "execution" in str(data).lower()


def test_execution_success_and_cooldown():
    _enable_execution()
    case = _create_case("anom-exec2", tenant="t1")
    # First execution
    r1 = client.post(f"/response/execute/{case['id']}", json={"action": "ticket"})
    assert r1.status_code == 200, r1.text
    # Immediate second should hit cooldown
    r2 = client.post(f"/response/execute/{case['id']}", json={"action": "ticket"})
    assert r2.status_code in (429, 400, 403)  # expecting cooldown 429
    # Sleep past cooldown
    time.sleep(1.1)
    r3 = client.post(f"/response/execute/{case['id']}", json={"action": "ticket"})
    assert r3.status_code == 200


def test_executive_dashboard_cache():
    update_param("executive.dashboard.cache_ttl_s", 5, reason="test")
    # First call -> miss
    r1 = client.get("/executive/dashboard")
    assert r1.status_code == 200
    data1 = r1.json()
    # Second call immediate -> should be hit (same snapshot reference values)
    r2 = client.get("/executive/dashboard")
    assert r2.status_code == 200
    data2 = r2.json()
    assert data1 == data2
