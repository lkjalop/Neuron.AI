import pytest, time
from config import runtime_params
from core.detect.snn import SNNDetector
from core.event import Event

def make_ev(i, val):
    return Event(event_id=f"ac{i}", timestamp=time.time(), event_type="ac", tenant_id="t0", features={"value": val}, trace_id=f"ac{i}")

@pytest.mark.parametrize("encoder", ["rate_v1", "rate_v2"])
def test_auto_calibration_threshold_adjusts(encoder):
    runtime_params.update_param("detection.enable_snn", True, reason="auto_cal_test")
    runtime_params.update_param("snn.encoder", encoder, reason="auto_cal_test")
    runtime_params.update_param("snn.auto_cal.enabled", True, reason="auto_cal_test")
    runtime_params.update_param("snn.auto_cal.interval", 60, reason="auto_cal_test")
    runtime_params.update_param("snn.auto_cal.target_ratio", 2.0, reason="auto_cal_test")
    runtime_params.update_param("snn.threshold", 1.0, reason="auto_cal_test_reset")
    det = SNNDetector()
    start_thr = det.threshold
    # Generate events with steadily increasing value to trigger anomalies
    for i in range(180):  # 3 calibration intervals
        ev = make_ev(i, i * 0.5)
        det.process(ev)
    end_thr = det.threshold
    # Threshold should have changed (either up or down depending on anomaly volume)
    assert end_thr != pytest.approx(start_thr), f"threshold did not adjust; start={start_thr} end={end_thr}"
    # Encoder name should reflect selection
    assert det.encoder_name == encoder
