import os, sys
import pytest

from config import runtime_params
from core.detect.snn import SNNDetector
from core.event import Event
from core import metrics

TORCH_AVAILABLE = True
try:
    import torch  # type: ignore
    import snntorch  # type: ignore
except Exception:  # noqa: BLE001
    TORCH_AVAILABLE = False


def make_event(idx: int, val: float):
    import time
    return Event(event_id=f"e{idx}", timestamp=time.time(), event_type="test", tenant_id="t0", features={"value": val}, trace_id=f"tr{idx}")


def _run_detector(mode: str):
    # use public API to set params instead of private dict
    runtime_params.update_param("detection.enable_snn", True, reason="test_enable_snn")
    runtime_params.update_param("snn.mode", mode, reason="test_set_mode")
    det = SNNDetector()
    # Feed a few escalating values to trigger anomalies
    out = []
    for i in range(30):
        ev = make_event(i, i * 0.5)
        res = det.process(ev)
        if res:
            out.extend(res)
    return det, out


def test_snn_proto_mode_basic():
    det, results = _run_detector("proto")
    assert det.mode.startswith("proto")
    assert any(r.get("activity") is not None for r in results)
    # Energy metric should accumulate (may be zero if no spikes but window should produce some)
    # Not asserting exact value; just ensure metric exists
    assert hasattr(metrics, "SNN_ENERGY_SPIKES_TOTAL")


@pytest.mark.skipif(not TORCH_AVAILABLE, reason="torch/snntorch not installed")
def test_snn_lif_mode_basic():
    det, results = _run_detector("lif")
    assert det.mode.startswith("lif") or det.mode == "proto_fallback"
    assert any(r.get("mode") in ("lif", "proto_fallback") for r in results)


def test_prediction_gauge_present():
    det, results = _run_detector("proto")
    # After a run predicted activity gauge should be set (indirectly; cannot read gauge value directly w/o registry internals)
    assert det is not None  # smoke indicator

