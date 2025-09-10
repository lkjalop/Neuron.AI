import math
import random
import time

from core.detect.isolation_forest import IsolationForestDetector, register_iforest
from core.detect.fusion import FusionArbitrator
from core.detect.baseline import BaselineDetector
from core.detect.interface import registry
from core.event import Event
from config import runtime_params


def _make_event(tenant: str, eid: int, v: float) -> Event:
    return Event(event_id=f"e{eid}", tenant_id=tenant, trace_id=f"t{eid}", features={"value": v})


def test_iforest_basic_retrain_and_anomaly_detection():
    runtime_params.update_param("iforest.enable", True, reason="test", actor="test")
    runtime_params.update_param("iforest.buffer_size", 128, reason="test", actor="test")
    runtime_params.update_param("iforest.retrain_interval_events", 16, reason="test", actor="test")
    runtime_params.update_param("iforest.retrain_interval_s", 0.0, reason="test", actor="test")
    runtime_params.update_param("iforest.min_train", 16, reason="test", actor="test")
    runtime_params.update_param("iforest.n_estimators", 50, reason="test", actor="test")
    runtime_params.update_param("iforest.max_samples", 64, reason="test", actor="test")
    runtime_params.update_param("iforest.contamination", 0.1, reason="test", actor="test")
    runtime_params.update_param("iforest.random_seed", 123, reason="test", actor="test")

    det = IsolationForestDetector()
    registry.register(det)
    tenant = "tenantA"
    # Generate mostly normal data ~ N(0,1)
    normal = [random.gauss(0, 1) for _ in range(64)]
    for i, v in enumerate(normal):
        det.process(_make_event(tenant, i, v))
    # Inject outliers
    outliers = [8.0, -7.5, 9.1]
    triggered = 0
    for j, v in enumerate(outliers, start=1000):
        res = det.process(_make_event(tenant, j, v))
        if res:
            triggered += 1
    # Expect at least one outlier flagged (probabilistic but should pass with contamination 0.1)
    assert triggered >= 1


def test_iforest_fusion_integration_weighted_sum():
    runtime_params.update_param("iforest.enable", True, reason="test", actor="test")
    runtime_params.update_param("iforest.buffer_size", 64, reason="test", actor="test")
    runtime_params.update_param("iforest.retrain_interval_events", 8, reason="test", actor="test")
    runtime_params.update_param("iforest.retrain_interval_s", 0.0, reason="test", actor="test")
    runtime_params.update_param("iforest.min_train", 8, reason="test", actor="test")
    runtime_params.update_param("iforest.n_estimators", 25, reason="test", actor="test")
    runtime_params.update_param("iforest.contamination", 0.15, reason="test", actor="test")
    runtime_params.update_param("fusion.weight.iforest", 0.3, reason="test", actor="test")
    runtime_params.update_param("detection.fusion.strategy", "weighted_sum", reason="test", actor="test")

    # Register detectors
    registry._reset_for_tests()  # type: ignore
    b = BaselineDetector(window=10, stddev_threshold=3.0)
    registry.register(b)
    iforest = register_iforest()
    arb = FusionArbitrator()
    tenant = "tenantF"
    # Warm-up baseline
    for i in range(12):
        evt = _make_event(tenant, i, random.gauss(0, 1))
        b_res = b.process(evt)
        i_res = iforest.process(evt)
        fused, meta = arb.fuse({"baseline": b_res, "iforest": i_res})
    # Inject extreme
    evt2 = _make_event(tenant, 999, 12.0)
    b_res2 = b.process(evt2)
    i_res2 = iforest.process(evt2)
    fused2, meta2 = arb.fuse({"baseline": b_res2, "iforest": i_res2})
    # At least one anomaly present and fusion score includes iforest weight for that anomaly
    flagged = [r for r in fused2 if r.get("detector") == "iforest"]
    assert flagged, "IsolationForest anomaly should appear in fused output"
    comp = flagged[0].get("fusion_components", {})
    assert "iforest_norm" in comp
    assert comp.get("weights", {}).get("w_if") == 0.3
