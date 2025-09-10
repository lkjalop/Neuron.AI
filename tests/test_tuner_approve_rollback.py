import os, time
from fastapi.testclient import TestClient
from core.main import app

client = TestClient(app)

os.environ.setdefault("ADMIN_API_KEY", "adminkey")

PARAM = "fusion.weighted_sum.suppress_threshold"


def test_tuner_approve_and_rollback_flow():
    # Approve new value
    r1 = client.post("/tuner/approve", json={"param": PARAM, "new_value": 0.42, "reason": "raise", "actor": "test_user"}, headers={"x-api-key": "adminkey"})
    assert r1.status_code == 200, r1.text
    js1 = r1.json()
    assert js1["status"] in ("applied", "recorded")
    assert js1["current"] == 0.42
    audit_id = js1.get("audit_id")
    assert audit_id
    # List changes
    r2 = client.get("/tuner/changes", headers={"x-api-key": "adminkey"})
    assert r2.status_code == 200
    items = r2.json()["items"]
    assert any(i.get("audit_id") == audit_id for i in items)
    # Rollback
    r3 = client.post(f"/tuner/rollback/{audit_id}", json={"actor": "test_user"}, headers={"x-api-key": "adminkey"})
    assert r3.status_code == 200, r3.text
    js3 = r3.json()
    assert js3["status"] in ("rolled_back", "recorded")
    assert "rollback_audit_id" in js3
    # Approve same value again -> noop
    r4 = client.post("/tuner/approve", json={"param": PARAM, "new_value": 0.42}, headers={"x-api-key": "adminkey"})
    assert r4.status_code == 200
    assert r4.json()["status"] in ("applied", "recorded", "noop")


def test_tuner_invalid_param():
    r = client.post("/tuner/approve", json={"param": "non.allowed.param", "new_value": 1}, headers={"x-api-key": "adminkey"})
    assert r.status_code == 400
    assert r.json().get("detail") in ("param_not_allowlisted", None) or r.json().get("error", {}).get("code") == "param_not_allowlisted"
