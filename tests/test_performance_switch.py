import os, json
import pytest
from fastapi.testclient import TestClient

# Import app
from core.main import app, require_api_key
from config.performance import ACTIVE_TIER, TIERS

@pytest.fixture
def client():
    return TestClient(app)

def test_performance_switch_audit(client, tmp_path, monkeypatch):
    # Monkeypatch audit path by changing CWD so audit/ writes into tmp space
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ADMIN_API_KEY", "test")
    # Override auth dependency to bypass API key enforcement
    app.dependency_overrides[require_api_key] = lambda: True
    # Choose a different tier than current
    current = ACTIVE_TIER.name
    target = next(t for t in TIERS.keys() if t != current)
    # Provide dummy API key header if auth dependency expects it (bypass if not enforced in test mode)
    body = {"tier": target}
    r = client.post("/config/performance/switch", json=body, headers={"x-api-key":"test"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["new"]["tier"] == target
    # Verify audit file
    audit_file = tmp_path / "audit" / "PERFORMANCE_TIER_SWITCH.jsonl"
    assert audit_file.exists(), "Audit file not created"
    lines = audit_file.read_text().strip().splitlines()
    assert lines, "Audit file empty"
    rec = json.loads(lines[-1])
    assert rec["new"] == target
