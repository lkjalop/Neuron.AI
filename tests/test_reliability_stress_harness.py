import statistics
import random
import asyncio
from core.pipeline import Pipeline
from core.event import Event
from config import runtime_params

# This stress harness focuses on stability of fused decision score presence and suppression variance


def _make_event(i: int, tenant: str = "tstress"):
    e = Event(event_id=f"st{i}", timestamp=0.0, event_type="test", tenant_id=tenant, features={"metric": random.random()}, trace_id=f"tr{i}")
    # Randomly tag some as noise to exercise precision proxy without triggering anomalies every time
    if i % 3 == 0:
        e.metadata = {"synthetic_pattern": "noise"}  # type: ignore[attr-defined]
    return e


def test_reliability_stress_variance():
    runtime_params.update_param("detection.enable_snn", True, reason="stress", actor="test")
    runtime_params.update_param("fusion.precision_window", 50, reason="stress", actor="test")
    p = Pipeline(["tstress"])  # Do not start async loop; manual flush
    # Inject a moderate batch of synthetic events
    for i in range(150):
        p.ingestion.queue.put_nowait(_make_event(i))  # type: ignore[attr-defined]
    asyncio.get_event_loop().run_until_complete(p.flush())
    # Inspect internal suppression history for variance
    hist = p._suppression_history.get("tstress", [])  # type: ignore[attr-defined]
    assert hist, "suppression history should not be empty"
    suppressed = [s for s,_ in hist]
    passed = [p_ for _,p_ in hist]
    # Basic variance bounds: should not be all suppressed or all passed after many events
    if len(suppressed) >= 10:
        rate_series = []
        tot_s = 0
        tot_p = 0
        for s,p_ in hist:
            tot_s += s
            tot_p += p_
            denom = tot_s + tot_p
            if denom:
                rate_series.append(tot_s/denom)
        if len(rate_series) >= 5:
            var = statistics.pvariance(rate_series)
            # Expect variance below a high threshold (indicates some stability) but not zero (no changes)
            assert var < 0.1
            assert var > 0.0

