from fastapi.testclient import TestClient
from src.core.main import app
from config import runtime_params
import uuid

client = TestClient(app)


def seed_params(n=25):
    for i in range(n):
        key = f"test.param.{i}"
        try:
            runtime_params.update_param("baseline.window_size", 50 + (i % 3), reason="seed", actor="test")  # ensure at least one valid update
        except Exception:
            pass
        # store synthetic via audit_agent_decision to increase map size without schema (can't update unknown keys)
        try:
            runtime_params.audit_agent_decision("seed", "note", {"k": key, "v": i})  # type: ignore[attr-defined]
        except Exception:
            pass


def test_diagnostics_pagination_basic():
    seed_params(40)
    r = client.get("/diagnostics/config?limit=10&offset=0")
    assert r.status_code == 200, r.text
    body = r.json()
    rt = body["runtime"]
    assert rt["limit"] == 10
    assert rt["offset"] == 0
    assert rt["returned"] <= 10
    assert "total" in rt and rt["total"] >= rt["returned"]
    # second page
    r2 = client.get("/diagnostics/config?limit=10&offset=10")
    assert r2.status_code == 200
    b2 = r2.json()["runtime"]
    assert b2["offset"] == 10
    assert b2["limit"] == 10
    # Ensure different slice (unless runtime map small)
    if rt["returned"] == 10 and b2["returned"] == 10:
        first_keys = {i['key'] for i in rt['items']}
        second_keys = {i['key'] for i in b2['items']}
        assert not first_keys.intersection(second_keys), "Pages should not fully overlap for sufficiently large map"


def test_diagnostics_full_map_flag():
    r = client.get("/diagnostics/config?full=true&limit=5")
    assert r.status_code == 200
    data = r.json()
    assert "runtime_full" in data
    assert isinstance(data["runtime_full"], dict)
    # runtime_full should be superset of paginated items
    paginated_keys = {itm['key'] for itm in data['runtime']['items']}
    assert paginated_keys.issubset(set(data['runtime_full'].keys()))


def test_diagnostics_auth_required_enforced(monkeypatch):
    # Set auth required flag and key
    runtime_params.update_param("diagnostics.auth.required", True, reason="test", actor="test")  # type: ignore[attr-defined]
    secret_key = uuid.uuid4().hex[:12]
    runtime_params.update_param("diagnostics.auth.key", secret_key, reason="test", actor="test")  # type: ignore[attr-defined]
    # Without header -> 401
    r = client.get("/diagnostics/config")
    assert r.status_code == 401
    # With header -> 200
    r2 = client.get("/diagnostics/config", headers={"x-diagnostics-key": secret_key})
    assert r2.status_code == 200
    # Disable requirement for cleanup
    runtime_params.update_param("diagnostics.auth.required", False, reason="cleanup", actor="test")  # type: ignore[attr-defined]

