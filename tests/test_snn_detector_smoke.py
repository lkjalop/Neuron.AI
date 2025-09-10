from __future__ import annotations
import os

import pytest

from core.event import Event
from detect.orchestrator import DetectorRegistry, Orchestrator, default_precision_proxy


@pytest.mark.skipif(os.environ.get("ENABLE_SNN", "false").lower() not in {"1", "true", "yes", "on"}, reason="SNN not enabled")
def test_snn_detector_optional_load():
    from detect.snn_detector import SNNDetector
    reg = DetectorRegistry()
    reg.register(SNNDetector(window=3, max_features=2))
    orch = Orchestrator(registry=reg, precision_proxy_fn=default_precision_proxy)
    ev = Event.create(event_type="x", severity=10.0, features={"f0": 1.0, "f1": 2.0}, tenant_id="t")
    anomalies = orch.process_event(ev)
    # First event may not produce anomaly (min/max not established) but should not error
    assert anomalies is not None
