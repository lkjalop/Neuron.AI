import os
import pytest
from fastapi.testclient import TestClient
from core.main import app

pytestmark = pytest.mark.skipif(not (os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL")), reason="DB not configured")

client = TestClient(app)


def _headers():
    return {"x-api-key": os.getenv("ADMIN_API_KEY", "adminkey")}


def test_vuln_db_vulnerabilities_filters():
    # Expect 200 even if empty; shape should be present
    r = client.get("/vuln/vulnerabilities?exploit_available=true&kev_listed=true", headers=_headers())
    assert r.status_code == 200
    js = r.json()
    assert "items" in js and "count" in js and js.get("source") in {"postgres", "memory"}


def test_vuln_db_findings_status_alias_and_state_change():
    # List by status alias (open)
    r = client.get("/vuln/findings?status=open", headers=_headers())
    assert r.status_code == 200
    js = r.json()
    assert "items" in js and "count" in js and js.get("source") in {"postgres", "memory"}
    # If there is at least one item and DB is active, attempt a state transition
    if js.get("source") == "postgres" and js.get("items"):
        fid = js["items"][0]["id"]
        r2 = client.post(f"/vuln/findings/{fid}/state", json={"state": "fixed", "reason": "test"}, headers=_headers())
        assert r2.status_code in (200, 503)  # 503 when store unavailable
