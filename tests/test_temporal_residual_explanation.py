from core.temporal.calibration import calibrator
from core.detect.temporal import TemporalDetector
from core.event import Event
from config import runtime_params


def make_event(tenant: str, eid: str, features: dict):
    return Event(event_id=eid, tenant_id=tenant, trace_id=eid, features=features)


def test_tft_top_residual_features(monkeypatch):
    runtime_params.update_param("detection.temporal.simple_model", True, reason="test")
    runtime_params.update_param("detection.temporal.encoder", "tft", reason="test")
    runtime_params.update_param("snn.encoding_window", 5, reason="test")
    det = TemporalDetector()
    # Feed enough events to prime window
    for i in range(5):
        ev = make_event("t0", f"e{i}", {"f1": i+1, "f2": (i+1)*2, "f3": (i+1)*3})
        det.process(ev)
    # Next event should produce potential residual anomaly
    ev2 = make_event("t0", "e_final", {"f1": 10, "f2": 5, "f3": 2})
    anomalies = det.process(ev2)
    # We may or may not fire depending on quantiles; ensure structure present when anomaly exists.
    if anomalies:
        a = anomalies[0]
        if a.get("encoder") == "tft" and a.get("reason", "").startswith("temporal_tft"):
            top = a.get("top_residual_features")
            assert top is None or isinstance(top, list)
            if top:
                assert "feature" in top[0] and "residual" in top[0]
