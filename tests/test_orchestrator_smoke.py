from __future__ import annotations

from detect.orchestrator import build_default_orchestrator
from core.event import Event


def test_orchestrator_baseline_anomaly_generation():
    orch = build_default_orchestrator()
    # Generate events with clear anomalies (large spikes)
    normal_events = [Event.create(event_type="t", severity=10.0 + (i % 3), tenant_id="t1") for i in range(60)]
    spike = Event.create(event_type="t", severity=50.0, tenant_id="t1")
    anomalies = []
    for ev in normal_events:
        orch.process_event(ev)
    anomalies.extend(orch.process_event(spike))
    assert any(a.detector == 'baseline_stats' for a in anomalies), "Expected baseline detector to flag spike"
