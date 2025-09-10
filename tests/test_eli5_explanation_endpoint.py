from fastapi.testclient import TestClient
from core.main import app, _create_case, _CASES
import time

def test_eli5_explanation_cache(monkeypatch):
    client = TestClient(app)
    c = _create_case("eli5-case-test", tenant="tcache")
    # first call should generate
    r1 = client.get(f"/explain/eli5/{c['id']}", headers={"x-api-key":"adminkey"})
    assert r1.status_code == 200, r1.text
    js1 = r1.json()
    assert js1["case_id"] == c['id']
    assert js1["cached"] is False
    assert "explanation" in js1 and isinstance(js1["explanation"], str)
    # second call should be cached (no refresh)
    r2 = client.get(f"/explain/eli5/{c['id']}", headers={"x-api-key":"adminkey"})
    assert r2.status_code == 200
    js2 = r2.json()
    assert js2["cached"] is True
    # force refresh
    r3 = client.get(f"/explain/eli5/{c['id']}?refresh=1", headers={"x-api-key":"adminkey"})
    assert r3.status_code == 200
    js3 = r3.json()
    assert js3["cached"] is False
    # invalid case
    r4 = client.get("/explain/eli5/does-not-exist", headers={"x-api-key":"adminkey"})
    assert r4.status_code == 404
