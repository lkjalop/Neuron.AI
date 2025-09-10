import pytest
from config import runtime_params
from core.pipeline import Pipeline
from core.event import Event
from core import metrics

@pytest.fixture(autouse=True)
def enable_snn(monkeypatch):
    runtime_params.update_param("detection.enable_snn", True, reason="test_noise_setup")
    runtime_params.update_param("detection.fusion.strategy", "pass_through", reason="test_noise_setup")
    # Ensure precision window small for fast metric change
    runtime_params.update_param("fusion.precision_window", 20, reason="test_noise_setup")
    yield


def test_noise_precision_proxy_counts():
    p = Pipeline(["t0"])  # do not start async loop; use flush path by injecting events directly
    # Inject synthetic noise events with metadata tag so pipeline logic counts them
    for i in range(10):
        ev = Event(event_id=f"n{i}", timestamp=0.0, event_type="test", tenant_id="t0", features={"value": 0.01}, trace_id=f"tr{i}")
        ev.metadata = {"synthetic_pattern": "noise"}  # type: ignore[attr-defined]
        p.ingestion.queue.put_nowait(ev)  # type: ignore[attr-defined]
    # Process synchronously
    import asyncio
    asyncio.get_event_loop().run_until_complete(p.flush())
    # Check windows counter (should equal number processed)
    windows_counter = metrics.PRECISION_PROXY_WINDOWS.labels(tenant="t0")._value.get()  # type: ignore[attr-defined]
    assert windows_counter >= 10
    # Rate gauge should exist even if zero anomalies
    _ = metrics.PRECISION_PROXY_RATE.labels(tenant="t0", detector="baseline")._value.get()  # type: ignore[attr-defined]
    _ = metrics.PRECISION_PROXY_RATE.labels(tenant="t0", detector="snn")._value.get()  # type: ignore[attr-defined]
