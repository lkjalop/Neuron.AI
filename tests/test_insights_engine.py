import time
from fastapi.testclient import TestClient
from core.main import app
from config import runtime_params
import os


def test_insights_endpoint_and_heuristics(monkeypatch):
    tenant = 'tenantA'
    # Configure params to trigger uplift deficit heuristic
    runtime_params.update_param('fusion.temporal.tuner.target_uplift', 2.0, reason='test', actor='test')
    # Simulate metrics values by monkeypatching gauge internal value objects if present
    # For simplicity we ensure uplift ratio below half target via direct param fallback (engine reads gauge best-effort)
    # Force calibration staleness threshold very low so any non-zero freshness triggers
    runtime_params.update_param('fusion.suppression_alert_rate', 1e-9, reason='test', actor='test')  # effectively force high suppression heuristic if rate >0
    # Simulate policy context quantile shift by calling snapshot twice with changed calibrator state if available
    # If calibrator is not providing real quantiles, we rely on delta logic being zero-tolerant; skip heavy mocking.

    client = TestClient(app)
    # Call endpoint (requires API key auth normally; override by setting expected env variable or monkeypatch dependency)
    # Easiest: monkeypatch require_api_key to no-op
    os.environ['ADMIN_API_KEY'] = 'testkey'
    resp = client.get(f"/insights?tenant={tenant}", headers={'x-api-key': 'testkey'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['tenant'] == tenant
    # At least one insight should appear (suppression high or uplift low)
    assert any(ins['category'] in {'temporal_uplift','fusion_suppression_high'} for ins in data['insights'])
    # Fusion weights structure present
    assert 'fusion_weights' in data
