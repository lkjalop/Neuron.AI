import pytest, math
from core.pipeline import Pipeline
from core.event import Event
from config import runtime_params
from core.detect.interface import registry

@pytest.mark.asyncio
async def test_mitre_like_periodic_shift_detection(monkeypatch):
    # Enable SNN and set fusion strategy pass_through to observe raw anomalies
    runtime_params.update_param('detection.enable_snn', True, reason='attack_sim')
    runtime_params.update_param('detection.fusion.strategy', 'pass_through', reason='attack_sim')
    # Lower baseline threshold to make it more sensitive for the test scenario
    runtime_params.update_param('baseline.stddev_threshold', 2.0, reason='attack_sim')
    p = Pipeline(['t_attack'])
    # Create periodic shift pattern: initial stable low values then sudden amplitude change
    benign = [Event(tenant_id='t_attack', features={'cpu': 1.0, 'mem': 1.0}) for _ in range(30)]
    attack = [Event(tenant_id='t_attack', features={'cpu': 10.0 + (i % 3), 'mem': 12.0 + (i % 5)}) for i in range(10)]
    for ev in benign + attack:
        p.ingestion.queue.put_nowait(ev)  # type: ignore
    import asyncio
    await p.flush()
    # Validate detectors registered
    baseline = registry.get('baseline')
    snn = registry.get('snn')  # May be None if SNN scaffold dependencies missing; allow pass
    assert baseline is not None
    # Inspect recent traces to ensure at least one detector fired during attack window
    from core.trace_store import traces
    recent = traces().recent(100)
    # Find any trace with fused_count >0 or detector fired after attack start (approx by index)
    fired = False
    if recent:
        # Attack events are last 10 enqueued; look at last 12 traces window
        for rec in recent[-15:]:
            fusion = rec.get('fusion', {})
            if fusion.get('fused_count', 0) > 0 or any(d.get('fired') for d in rec.get('detectors', [])):
                fired = True
                break
    assert fired, "Expected at least one anomaly trace during simulated attack sequence"
