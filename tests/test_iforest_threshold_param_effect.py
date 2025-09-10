from core.detect.isolation_forest import IsolationForestDetector
from core.detect.interface import registry
from core.event import Event
from config import runtime_params


def _evt(v, i):
    return Event(event_id=f"e{i}", tenant_id="tenantT", trace_id=f"tr{i}", features={"value": v})


def test_iforest_extreme_threshold_param_effect():
    # Lower threshold to force more heuristic anomalies
    registry._reset_for_tests()  # type: ignore
    runtime_params.update_param("iforest.enable", True, reason="test", actor="test")
    runtime_params.update_param("iforest.min_train", 1000000, reason="test", actor="test")  # prevent model training noise
    det_low = IsolationForestDetector()
    registry.register(det_low)
    runtime_params.update_param("iforest.extreme_value_threshold", 5.0, reason="test", actor="test")
    low_trigger = sum(bool(det_low.process(_evt(v, i))) for i, v in enumerate([4.0, 5.1, 6.2, -7.3, 3.0, 5.5]))

    # Reset and raise threshold (fewer anomalies expected)
    registry._reset_for_tests()  # type: ignore
    det_high = IsolationForestDetector()
    runtime_params.update_param("iforest.extreme_value_threshold", 8.0, reason="test", actor="test")
    runtime_params.update_param("iforest.enable", True, reason="test", actor="test")
    runtime_params.update_param("iforest.min_train", 1000000, reason="test", actor="test")
    registry.register(det_high)
    high_trigger = sum(bool(det_high.process(_evt(v, i))) for i, v in enumerate([4.0, 5.1, 6.2, -7.3, 3.0, 5.5]))

    assert low_trigger > high_trigger, f"Expected more anomalies with lower threshold: low={low_trigger} high={high_trigger}"
