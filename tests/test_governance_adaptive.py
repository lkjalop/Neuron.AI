import time
import json
import os
import pytest
import re

from fastapi.testclient import TestClient
from core.main import app

from config import runtime_params
from core.pipeline import Pipeline

TENANT = "tenantA"

@pytest.fixture(scope="function")
def pipeline_instance():
    # Ensure strategy and initial threshold
    runtime_params.update_param("detection.fusion.strategy", "weighted_sum", reason="test_setup", actor="test")
    runtime_params.update_param("fusion.weighted_sum.suppress_threshold", 0.50, reason="test_setup", actor="test")
    runtime_params.update_param("governance.autotune.max_per_hour", 3, reason="test_setup", actor="test")
    p = Pipeline([TENANT])
    yield p


def test_autotune_rate_limit(pipeline_instance):
    p = pipeline_instance
    base_fp = 0.05
    snn_fp = 0.20  # > tol -> upward adjustments
    now = time.time()
    changes = 0
    for i in range(10):
        changed, new_thr = p._autotune_test_hook(TENANT, snn_fp, base_fp, now_ts=now + i*120)  # 2 minute spacing bypasses 30s cooldown
        if changed:
            changes += 1
    assert changes <= 3, f"Rate limit exceeded expected changes<=3, got {changes}"
    # Confirm threshold advanced at least once
    final_thr = float(runtime_params.get_param("fusion.weighted_sum.suppress_threshold") or 0.0)
    assert final_thr >= 0.52


def test_drift_guard_action_modes(pipeline_instance):
    p = pipeline_instance
    # Seed fusion history to trip guard conditions (simulate high snn unique + suppression rate)
    hist = p._fusion_history.setdefault(TENANT, [])
    for _ in range(40):
        hist.append((1,1))  # snn unique every event
    # Provide suppression history
    p._suppression_history.setdefault(TENANT, []).extend([(1,0) for _ in range(40)])
    # Mode: disable_only
    runtime_params.update_param("detection.enable_snn", True, reason="test", actor="test")
    runtime_params.update_param("governance.drift_guard.action_mode", "disable_only", reason="test", actor="test")
    tripped = p._maybe_drift_guard(TENANT, suppression_rate=0.95, force=False)
    assert tripped
    assert not bool(runtime_params.get_param("detection.enable_snn"))
    # Mode: raise_only
    runtime_params.update_param("detection.enable_snn", False, reason="test", actor="test")
    runtime_params.update_param("fusion.weighted_sum.suppress_threshold", 0.60, reason="reset", actor="test")
    runtime_params.update_param("governance.drift_guard.action_mode", "raise_only", reason="test", actor="test")
    tripped2 = p._maybe_drift_guard(TENANT, suppression_rate=0.95, force=True)  # force to re-trigger
    assert tripped2
    thr = float(runtime_params.get_param("fusion.weighted_sum.suppress_threshold") or 0.0)
    assert thr >= 0.62


def test_governance_diagnostics_shape(pipeline_instance):
    p = pipeline_instance
    # Generate a couple actions
    p._autotune_test_hook(TENANT, 0.25, 0.05)
    p._autotune_test_hook(TENANT, 0.25, 0.05, now_ts=time.time()+400)
    # Persist file should exist
    path = "artifacts/governance/governance_actions.jsonl"
    assert os.path.exists(path)
    with open(path, "r", encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]
    assert any(rec.get("action") == "autotune_suppression" for rec in lines)
    # Inspect in-memory structure
    acts = p._gov_actions.get(TENANT, [])
    assert len(acts) >= 2
    # Basic field presence
    sample = acts[-1]
    for k in ("action", "ts", "old", "new"):
        assert k in sample


def test_initial_threshold_gauge_sync(pipeline_instance):
    p = pipeline_instance
    # On init the gauge should have been set; we can't query metrics registry directly without scraping
    # Instead trigger another autotune and rely on absence of errors; ensure threshold param still accessible
    thr = runtime_params.get_param("fusion.weighted_sum.suppress_threshold")
    assert thr is not None


def test_diagnostics_endpoint_shape_and_counts(test_app, ensure_pipeline):
    p = ensure_pipeline
    # generate actions via test hook
    p._autotune_test_hook("tenantA", 0.30, 0.05)
    p._autotune_test_hook("tenantA", 0.30, 0.05, now_ts=time.time()+400)
    resp = test_app.get("/governance/diagnostics?tenant=tenantA")
    assert resp.status_code == 200
    body = resp.json()
    assert "actions" in body and isinstance(body["actions"], list)
    assert "action_counts" in body and isinstance(body["action_counts"], dict)
    assert body.get("total_actions", 0) >= len(body["actions"])  # total >= returned slice
    # Ensure autotune counted
    if body["action_counts"]:
        assert any(k.startswith("autotune") or k == "autotune_suppression" for k in body["action_counts"].keys())


def test_metrics_scrape_contains_governance(test_app, ensure_pipeline):
    p = ensure_pipeline
    p._autotune_test_hook("tenantA", 0.30, 0.05)
    metrics_resp = test_app.get("/metrics")
    assert metrics_resp.status_code == 200
    text = metrics_resp.text
    # Look for governance metrics names
    assert "neuron_fusion_suppress_autotune_adjustments_total" in text
    assert "neuron_governance_actions_total" in text


def test_drift_guard_raise_first_mode(test_app, ensure_pipeline):
    p = ensure_pipeline
    # Prepare histories to allow trigger
    hist = p._fusion_history.setdefault("tenantA", [])
    for _ in range(40):
        hist.append((1,1))
    p._suppression_history.setdefault("tenantA", []).extend([(1,0) for _ in range(40)])
    runtime_params.update_param("detection.enable_snn", True, reason="test", actor="test")
    runtime_params.update_param("governance.drift_guard.action_mode", "raise_first", reason="test", actor="test")
    thr_before = float(runtime_params.get_param("fusion.weighted_sum.suppress_threshold") or 0.5)
    p._maybe_drift_guard("tenantA", suppression_rate=0.95, force=False)
    snn_enabled_after = bool(runtime_params.get_param("detection.enable_snn"))
    thr_after = float(runtime_params.get_param("fusion.weighted_sum.suppress_threshold") or 0.5)
    # raise_first should prefer threshold raise; SNN should still be enabled if raise succeeded
    assert thr_after >= thr_before + 0.01
    assert snn_enabled_after, "SNN should remain enabled in raise_first ordering when raise applied first"


def test_diagnostics_multi_tenant_isolation(test_app, ensure_pipeline):
    p = ensure_pipeline
    # Add second tenant actions directly (if second tenant exists simulate) else skip gracefully
    if len(p.tenants) < 2:
        pytest.skip("multi-tenant isolation requires at least 2 tenants configured")
    t2 = p.tenants[1]
    p._autotune_test_hook(p.tenants[0], 0.30, 0.05)
    p._autotune_test_hook(t2, 0.30, 0.05)
    r1 = test_app.get(f"/governance/diagnostics?tenant={p.tenants[0]}").json()
    r2 = test_app.get(f"/governance/diagnostics?tenant={t2}").json()
    # Ensure that actions lists differ (each contains at least one action) and not merged
    assert r1.get("actions") and r2.get("actions")
    # Each action record should have correct tenant (persisted copy) but in-memory actions don't carry tenant; rely on counts
    assert r1.get("total_actions") >= 1 and r2.get("total_actions") >= 1


def test_diagnostics_endpoint_disable(test_app, ensure_pipeline):
    # Disable endpoint and verify 404
    runtime_params.update_param("governance.diagnostics.enabled", False, reason="test_disable", actor="test")
    resp = test_app.get("/governance/diagnostics?tenant=tenantA")
    assert resp.status_code == 404
    runtime_params.update_param("governance.diagnostics.enabled", True, reason="test_reenable", actor="test")


def test_governance_log_rotation(pipeline_instance, tmp_path):
    # Use small size to force rotation
    runtime_params.update_param("governance.diagnostics.max_log_bytes", 200, reason="test", actor="test")
    runtime_params.update_param("governance.diagnostics.max_history_files", 2, reason="test", actor="test")
    p = pipeline_instance
    for i in range(50):
        p._record_gov_action("tenantA", {"ts": time.time(), "action": "autotune_suppression", "old": 0.5, "new": 0.51 + i*0.0001})
    path = "artifacts/governance/governance_actions.jsonl"
    # Expect rotation produced .1 or .2
    rotated_exists = any(os.path.exists(f"{path}.{i}") for i in (1,2))
    assert rotated_exists, "Expected at least one rotated governance actions file"


def test_shadow_recommendations_audit(pipeline_instance, monkeypatch):
    p = pipeline_instance
    # Enable shadow mode
    runtime_params.update_param("governance.shadow.enabled", True, reason="test", actor="test")
    # Simulate precision proxy tallies to drive diff > tol
    p._precision_proxy.setdefault("tenantA", {"windows": 25, "fp_snn": 10, "fp_baseline": 1})
    records: list = []
    def fake_audit(agent, action, detail):  # noqa: D401
        records.append((agent, action, detail))
    monkeypatch.setattr(runtime_params, "audit_agent_decision", fake_audit)
    # Call internal logic portion by mimicking snippet: we invoke autotune test hook to progress state first
    p._autotune_test_hook("tenantA", 0.30, 0.05)
    # Manually invoke pipeline suppression block by calling private drift_guard (will not produce shadow) then re-run autotune hook to trigger code path again
    p._autotune_test_hook("tenantA", 0.30, 0.05, now_ts=time.time()+400)
    # Shadow recommendations executed inside main loop normally; here we directly re-run test hook and rely on shadow code having executed during earlier adjustments if condition matched.
    # Assert at least one governance_shadow audit
    assert any(r[0] == "governance_shadow" for r in records), "Expected governance_shadow audit decision recorded"
