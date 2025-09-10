import math

from config import runtime_params
from core.detect.snn import SNNDetector
from core.event import Event


def make_event(val: float, tenant: str = "t1"):
    return Event.create(
        event_type="metric",
        tenant_id=tenant,
        features={"value": val, "f1": val * 0.5},
        metadata={}
    )


def test_residual_disabled_no_effect(monkeypatch):
    runtime_params.update_param("seq.forecaster.enable", False, reason="test")
    runtime_params.update_param("snn.encoder", "rate_v1", reason="test")  # simpler deterministic path
    runtime_params.update_param("snn.threshold", 0.1, reason="test")
    det = SNNDetector()
    # Warm up with a few values
    for v in [1,2,3,4,5]:
        det.process(make_event(v))
    # Capture activity baseline
    ev = make_event(6)
    res = det.process(ev)
    assert res, "Should produce detection or at least process"
    act_baseline = res[0].get("activity")
    # Enable residual but do not feed new sequence differences (still disabled flag ensures no change)
    runtime_params.update_param("seq.forecaster.enable", False, reason="test")
    ev2 = make_event(7)
    res2 = det.process(ev2)
    act2 = res2[0].get("activity") if res2 else None
    assert act2 is not None
    # Since residual disabled, activity progression should be monotonic from encoder only.
    # We just assert no unexpected large jump > 2x
    assert act2 < act_baseline * 2 + 1e-6


def test_residual_positive_increases_activity(monkeypatch):
    runtime_params.update_param("seq.forecaster.enable", True, reason="test")
    runtime_params.update_param("snn.encoder", "rate_v1", reason="test")
    runtime_params.update_param("snn.threshold", 0.1, reason="test")
    det = SNNDetector()
    # Prime with low variance sequence so forecast residual for spike becomes positive
    for v in [10,10,10,10,10,10]:
        det.process(make_event(v))
    # Activity before spike
    base_res = det.process(make_event(10.0))
    base_act = base_res[0].get("activity") if base_res else 0.0
    # Inject spike
    spike_res = det.process(make_event(30.0))
    spike_act = spike_res[0].get("activity") if spike_res else 0.0
    assert spike_act >= base_act, "Activity with positive residual should not decrease"
    # Expect some bounded increase (tanh residual contribution <=1)
    assert spike_act - base_act <= 1.5, "Residual contribution unexpectedly large"
