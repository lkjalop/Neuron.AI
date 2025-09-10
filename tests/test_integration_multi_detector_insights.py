import random
from fastapi.testclient import TestClient
from core.main import app
from core.detect.interface import registry
from core.detect.baseline import BaselineDetector
from core.detect.isolation_forest import register_iforest
from core.detect.fusion import FusionArbitrator
from core.event import Event
from config import runtime_params


def _evt(t, i, v):
    return Event(event_id=f"e{i}", tenant_id=t, trace_id=f"tr{i}", features={"value": v})


def test_multi_detector_fusion_and_insights_severity():
    tenant = "tenantM"
    # Enable detectors and configure fusion weighted_sum to involve iforest
    runtime_params.update_param("iforest.enable", True, reason="test", actor="test")
    runtime_params.update_param("iforest.buffer_size", 64, reason="test", actor="test")
    runtime_params.update_param("iforest.retrain_interval_events", 8, reason="test", actor="test")
    runtime_params.update_param("iforest.retrain_interval_s", 0.0, reason="test", actor="test")
    runtime_params.update_param("iforest.min_train", 8, reason="test", actor="test")
    runtime_params.update_param("iforest.n_estimators", 25, reason="test", actor="test")
    runtime_params.update_param("iforest.contamination", 0.15, reason="test", actor="test")
    runtime_params.update_param("fusion.weight.iforest", 0.35, reason="test", actor="test")
    runtime_params.update_param("detection.fusion.strategy", "weighted_sum", reason="test", actor="test")
    # Suppression alert threshold very low so suppression insight can trigger if any suppression occurs
    runtime_params.update_param("fusion.suppression_alert_rate", 1e-9, reason="test", actor="test")
    # Uplift target high to force low uplift severity
    runtime_params.update_param("fusion.temporal.tuner.target_uplift", 2.0, reason="test", actor="test")

    registry._reset_for_tests()  # type: ignore
    base = BaselineDetector(window=10, stddev_threshold=3.0)
    registry.register(base)
    iforest = register_iforest()
    arb = FusionArbitrator()

    # Warm up baseline + iforest buffer
    for i in range(12):
        v = random.gauss(0, 1)
        e = _evt(tenant, i, v)
        b_res = base.process(e)
        i_res = iforest.process(e)
        arb.fuse({"baseline": b_res, "iforest": i_res})

    # Inject extreme value to ensure iforest anomaly
    extreme_evt = _evt(tenant, 999, 15.0)
    b_res2 = base.process(extreme_evt)
    i_res2 = iforest.process(extreme_evt)
    fused, meta = arb.fuse({"baseline": b_res2, "iforest": i_res2})
    # Ensure isolation forest anomaly present
    assert any(r.get("detector") == "iforest" for r in fused)

    # Call insights endpoint
    import os
    os.environ['ADMIN_API_KEY'] = 'testkey'
    client = TestClient(app)
    resp = client.get(f"/insights?tenant={tenant}", headers={'x-api-key': 'testkey'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['tenant'] == tenant
    # Insights include severity field
    assert all('severity' in i for i in data['insights'])
    # At least one severity > 0 (uplift or suppression or quantile shift)
    assert any((i.get('severity',0)>0) for i in data['insights'])
    # Fusion weights include iforest weight
    assert data['fusion_weights'].get('fusion.weight.iforest') == 0.35
