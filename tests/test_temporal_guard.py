from config import runtime_params
from core.pipeline import Pipeline
from core.detect.interface import registry
from core.event import Event
from core import metrics


def test_temporal_guard_noop_stub_latency():
    runtime_params.update_param('detection.temporal.enable_transformer', True, reason='guard_test')
    # Use minimum allowed latency threshold (schema lower bound is 0.01) to emulate future guard sensitivity
    runtime_params.update_param('temporal.guard.max_latency_s', 0.01, reason='guard_test')
    p = Pipeline(['t_guard'])
    temporal = registry.get('temporal')
    assert temporal is not None
    # Process a few events (stub returns instantly; we can't force real latency but test path doesn't raise)
    for i in range(3):
        temporal.process(Event(tenant_id='t_guard', features={'cpu': 1.0, 'mem': 1.0}))  # type: ignore
    # Metric presence check
    assert hasattr(metrics, 'TEMPORAL_LATENCY')