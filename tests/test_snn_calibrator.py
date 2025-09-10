import time, pytest
from config import runtime_params
from core.detect.snn import SNNDetector
from core.event import Event


def make_ev(i, val):
    return Event(event_id=f"ac{i}", timestamp=time.time(), event_type="ac", tenant_id="t0", features={"value": val}, trace_id=f"ac{i}")

@pytest.fixture(autouse=True)
def reset_params():
    # Ensure defaults each test
    runtime_params.update_param("detection.enable_snn", True, reason="cal_test")
    runtime_params.update_param("snn.threshold", 1.0, reason="cal_test")
    runtime_params.update_param("snn.auto_cal.enabled", True, reason="cal_test")
    runtime_params.update_param("snn.auto_cal.interval", 60, reason="cal_test")
    runtime_params.update_param("snn.auto_cal.target_ratio", 2.0, reason="cal_test")
    runtime_params.update_param("snn.auto_cal.max_step", 0.3, reason="cal_test")
    yield


def run_events(det: SNNDetector, values):
    for i, v in enumerate(values):
        det.process(make_ev(i, v))


def test_calibration_increases_threshold_when_uplift_high():
    det = SNNDetector()
    start = det.threshold
    # Simulate many anomalies vs small baseline (baseline placeholder is 0 -> uplift large)
    # Provide consistent increasing values to ensure score > 0
    run_events(det, [i * 0.5 for i in range(120)])  # two intervals (interval=60)
    end = det.threshold
    assert end > start, f"expected threshold to increase; start={start} end={end}"


def test_calibration_decreases_threshold_when_zero_anomalies():
    # Force no anomalies by setting high starting threshold
    runtime_params.update_param("snn.threshold", 6.0, reason="cal_test")
    det = SNNDetector()
    start = det.threshold
    # Values too small to cross threshold
    run_events(det, [0.1 for _ in range(120)])
    end = det.threshold
    assert end < start, f"expected threshold to decrease to increase sensitivity; start={start} end={end}"


def test_calibration_increase_uplift_when_below_deadband():
    # Scenario: uplift well below target -> expect increase_uplift adjustment
    det = SNNDetector()
    det._baseline_anoms_seen = 50  # larger baseline to pull uplift ratio toward target
    # Craft pattern: first half low (no anomalies), second half moderate (some anomalies)
    vals = [0.1 for _ in range(60)] + [0.6 if (i % 3) == 0 else 0.4 for i in range(60)]
    for i, v in enumerate(vals):
        det.process(make_ev(i, v))
    decision = det._last_cal_decision
    assert decision is not None, "expected calibration decision"
    assert decision.reason == "increase_uplift", f"expected increase_uplift; got {decision.reason}"


def test_encoder_selection_passthrough():
    runtime_params.update_param("snn.encoder", "rate_v2", reason="enc_test")
    det = SNNDetector()
    assert det.encoder_name == "rate_v2"
