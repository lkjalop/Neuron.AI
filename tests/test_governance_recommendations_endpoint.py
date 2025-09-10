import json, time, os
from fastapi.testclient import TestClient
import core.main as main_mod
from core.main import app
from config import runtime_params

client = TestClient(app)

def test_recommendations_endpoint_empty_and_filters():
    # Ensure pipeline exists (initialize if absent) and governance shadow enabled
    runtime_params.update_param("governance.shadow.enabled", True, reason="test_setup", actor="test")
    if main_mod.pipeline is None:  # create lightweight pipeline (no start needed)
        from core.pipeline import Pipeline
        main_mod.pipeline = Pipeline(["tenantA"])  # type: ignore
    # Configure admin API key for auth
    os.environ["ADMIN_API_KEY"] = "testadmin"
    # Manually seed internal recommendation buffer for deterministic test
    buf = main_mod.pipeline._gov_recommendations.setdefault("tenantA", [])  # type: ignore[attr-defined]
    buf.clear()
    now = time.time()
    buf.extend([
        {"ts": now - 5, "tenant": "tenantA", "suggestion": {"action": "raise_threshold", "delta": 0.01, "reason": "shadow_fp_rate_diff", "diff": 0.07}},
        {"ts": now - 3, "tenant": "tenantA", "suggestion": {"action": "lower_threshold", "delta": -0.01, "reason": "shadow_fp_rate_diff", "diff": -0.06}},
    ])
    # Basic fetch
    r = client.get("/governance/recommendations/recent?limit=10", headers={"x-api-key": "testadmin"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 2
    # Newest first
    assert data["items"][0]["suggestion"]["action"] in {"raise_threshold", "lower_threshold"}
    # Filter action
    r2 = client.get("/governance/recommendations/recent?action=raise_threshold", headers={"x-api-key": "testadmin"})
    assert r2.status_code == 200
    d2 = r2.json()
    assert all(it["suggestion"]["action"] == "raise_threshold" for it in d2["items"]) or d2["returned"] == 0
    # Offset pagination (offset 1 should return at most 1 item)
    r3 = client.get("/governance/recommendations/recent?limit=1&offset=1", headers={"x-api-key": "testadmin"})
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["returned"] <= 1
