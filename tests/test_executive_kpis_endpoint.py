import pytest
from core.main import app, executive_agg
from fastapi.testclient import TestClient
import os

def _set_admin_env(monkeypatch):
    monkeypatch.setenv('ADMIN_API_KEY', 'secret')

@pytest.mark.asyncio
async def test_executive_kpis_snapshot(monkeypatch):
    _set_admin_env(monkeypatch)
    client = TestClient(app)
    # Prime aggregator with synthetic data
    executive_agg.record_fusion(0.5, 0.2, 0.1)
    executive_agg.record_anomalies(baseline=3, snn=2)
    executive_agg.record_param_change()
    resp = client.get('/executive/kpis', headers={'x-api-key': 'secret'})
    assert resp.status_code == 200
    data = resp.json()
    assert 'fusion' in data and 'detection' in data and 'governance' in data
    assert data['fusion']['overlap_ratio_avg'] >= 0.0
