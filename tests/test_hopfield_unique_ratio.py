import time
from core.detect.fusion import FusionArbitrator
from core.hopfield.memory import hopfield_instance
from core import metrics

# Minimal DetectionResult type alias (dict-based in codebase)

def _mk(detector: str, eid: int, tenant: str = "t1"):
    return {"detector": detector, "event_id": eid, "tenant": tenant, "threshold": 1.0, "activity": 2.0}

def test_hopfield_unique_ratio_export():
    arb = FusionArbitrator()
    mem = hopfield_instance()  # ensure initialized
    # Create baseline anomalies for events 1..3
    baseline = [_mk("baseline", i) for i in range(1,4)]
    # Hopfield anomalies for events 4..6 (unique) + one overlapping with baseline (event 2) to test union logic
    hopfield = [_mk("hopfield", i) for i in [2,4,5,6]]
    fused, meta = arb._weighted_sum({"baseline": baseline, "hopfield": hopfield})  # type: ignore
    assert fused, "Expected fused anomalies to be non-empty"
    # Scrape metric value (best-effort by accessing internal _metrics of Gauge)
    g = metrics.HOPFIELD_UNIQUE_RATIO
    val = 0.0
    for _k, child in getattr(g, '_metrics', {}).items():  # type: ignore[attr-defined]
        val = float(child._value.get())  # type: ignore
    # Unique hopfield events should be 3 (4,5,6) over union (baseline 1..3 plus hopfield 4..6 => 6 total) => 0.5
    assert 0.49 < val < 0.51, f"Unexpected hopfield unique ratio {val}" 
