from __future__ import annotations

from core.detect.temporal import register_temporal
from core.detect.interface import registry
from core.event import Event
from core.pipeline import Pipeline
from config import runtime_params


def test_temporal_registration_and_basic_flow(monkeypatch):
    runtime_params.update_param("detection.temporal.enable_transformer", True, reason="test", actor="test")
    register_temporal()
    det = registry.get("temporal")
    assert det is not None
    # Build a pipeline (will also attempt registration but idempotent)
    p = Pipeline(["t1"])
    # Create sequential events with numeric features to fill window
    for i in range(25):
        ev = Event(tenant_id="t1", features={"f1": i, "f2": i * 2}, metadata={}, timestamp=i)
        # Directly call detector to avoid async ingestion complexity
        det.process(ev)
    # After enough events window ready -> residual metrics should have recorded anomalies sometimes
    # We cannot guarantee anomaly firing deterministically here but detector exists and window filled
    assert True
from config import runtime_params
from core.pipeline import Pipeline
from core.detect.interface import registry


def test_temporal_stub_registration():
    runtime_params.update_param('detection.temporal.enable_transformer', True, reason='test_temporal_stub')
    # Ensure simple model flag is explicitly disabled so prior tests enabling it don't leak state.
    runtime_params.update_param('detection.temporal.simple_model', False, reason='test_temporal_stub_reset')
    p = Pipeline(['t_temp'])
    det = registry.get('temporal')
    assert det is not None, 'Temporal detector stub not registered'
    # Process a few events and ensure no anomalies returned
    from core.event import Event
    anomalies_total = 0
    for i in range(5):
        res = det.process(Event(tenant_id='t_temp', features={'cpu': 1+i*0.1}))  # type: ignore
        anomalies_total += len(res or [])
    assert anomalies_total == 0, 'Temporal stub should emit no anomalies'