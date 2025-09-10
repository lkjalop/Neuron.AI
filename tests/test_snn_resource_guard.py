import time
from config import runtime_params
from core.detect.snn import SNNDetector, evaluate_resource_guard
from core.event import Event


def make_event(n: int = 5):
    # Create simple event with numeric features to induce spikes
    features = {f"f{i}": i + 1 for i in range(n)}
    return Event(event_id="e", tenant_id="t", trace_id="tr", features=features, raw={})


def test_resource_guard_latency_trigger(monkeypatch):
    det = SNNDetector()
    # Simulate high latency samples
    samples = [0.5] * 10
    assert evaluate_resource_guard(samples, 0.1) is True


def test_resource_guard_density_trigger():
    samples = [0.01] * 10
    assert evaluate_resource_guard(samples, 0.95) is True


def test_detector_cooldown(monkeypatch):
    # Lower cooldown for test speed
    runtime_params.update_param("snn.guard.cooldown_s", 1.0, reason="test", actor="test")
    det = SNNDetector()
    # Force guard by monkeypatching evaluate_resource_guard to True first call
    called = {"n": 0}
    from core.detect import snn as snn_mod

    orig_eval = snn_mod.evaluate_resource_guard

    def fake_eval(lat, dens):
        called["n"] += 1
        return called["n"] == 1

    snn_mod.evaluate_resource_guard = fake_eval
    e = make_event()
    # First call triggers guard and returns []
    assert det.process(e) == []
    assert det._disabled_until is not None
    # Second call still within cooldown -> []
    assert det.process(e) == []
    # Advance time beyond cooldown
    time.sleep(1.1)
    # Third call should attempt processing; monkeypatch returns False now
    snn_mod.evaluate_resource_guard = lambda lat, dens: False
    res = det.process(e)
    assert isinstance(res, list)
    snn_mod.evaluate_resource_guard = orig_eval
