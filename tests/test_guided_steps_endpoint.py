from fastapi.testclient import TestClient
from core.main import app, _create_case

def test_guided_steps_basic(monkeypatch):
    client = TestClient(app)
    # create synthetic case
    c = _create_case("case-guided-test", tenant="t1")
    r = client.get(f"/guided/steps/{c['id']}?limit=5", headers={"x-api-key":"adminkey"})
    assert r.status_code == 200, r.text
    js = r.json()
    assert js["case_id"] == c['id']
    assert "steps" in js and isinstance(js["steps"], list)
    assert js["count"] == len(js["steps"])
    # limit enforcement
    r2 = client.get(f"/guided/steps/{c['id']}?limit=1", headers={"x-api-key":"adminkey"})
    assert r2.status_code == 200
    assert r2.json()["count"] <= 1
