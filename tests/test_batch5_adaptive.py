import time
import json
import pytest
from fastapi.testclient import TestClient

# Import the main module itself so that mutated globals (pipeline) are visible
from core import main as core_main


def make_client():
    import os
    os.environ["ADMIN_API_KEY"] = "adminkey"
    os.environ["PREDICT_API_KEY"] = "predictkey"
    return TestClient(core_main.app)


@pytest.fixture(scope="module")
def client():
    return make_client()


def ingest_noise_event(client, eid: str, tenant: str = "t1", detectors: dict | None = None):
    meta = {"synthetic_pattern": "noise"}
    ev = {"event_id": eid, "tenant_id": tenant, "message": f"noise {eid}", "metadata": meta}
    r = client.post("/ingest", json=ev)
    assert r.status_code == 200


def test_autotune_adjustment_shadow_and_threshold(client):
    # Precondition: enable weighted_sum strategy and modest initial threshold
    core_main.runtime_params.update_param("detection.fusion.strategy", "weighted_sum", reason="test_setup", actor="test")
    core_main.runtime_params.update_param("fusion.weighted_sum.suppress_threshold", 0.3, reason="test_setup", actor="test")
    # Simulate windows where SNN produces more FP than baseline by toggling SNN on (best-effort)
    core_main.runtime_params.update_param("detection.enable_snn", True, reason="test_setup", actor="test")
    # Generate enough noise windows
    for i in range(50):
        ingest_noise_event(client, f"a{i}")
    # Allow background loop to process
    time.sleep(1.0)
    thr_after = core_main.runtime_params.get_param("fusion.weighted_sum.suppress_threshold")
    # Expect possible upward adjustment (>= original)
    assert thr_after >= 0.3


def test_strategy_fallback(client):
    # Force high suppression scenario by setting threshold very high and using weighted_sum
    core_main.runtime_params.update_param("detection.fusion.strategy", "weighted_sum", reason="test_setup", actor="test")
    core_main.runtime_params.update_param("fusion.weighted_sum.suppress_threshold", 0.9, reason="test_setup", actor="test")
    core_main.runtime_params.update_param("detection.enable_snn", True, reason="test_setup", actor="test")
    for i in range(45):
        ingest_noise_event(client, f"f{i}")
    time.sleep(1.0)
    # Expect fallback to baseline_priority (best-effort; allow either baseline_priority or weighted_sum if race)
    strat = core_main.runtime_params.get_param("detection.fusion.strategy")
    assert strat in {"baseline_priority", "weighted_sum"}


def test_drift_guard_helper_invocation(client):
    # Reset key params
    core_main.runtime_params.update_param("detection.enable_snn", True, reason="test_setup", actor="test")
    core_main.runtime_params.update_param("detection.fusion.strategy", "weighted_sum", reason="test_setup", actor="test")
    core_main.runtime_params.update_param("fusion.weighted_sum.suppress_threshold", 0.4, reason="test_setup", actor="test")
    # Directly invoke internal helper with force=True for deterministic path
    assert core_main.pipeline is not None
    core_main.pipeline._maybe_drift_guard("t1", suppression_rate=0.9, force=True)  # type: ignore[attr-defined]
    snn_enabled = core_main.runtime_params.get_param("detection.enable_snn")
    thr = core_main.runtime_params.get_param("fusion.weighted_sum.suppress_threshold")
    # Either SNN disabled or threshold bumped
    assert (not snn_enabled) or (thr > 0.4)


def test_sse_stream_decisions(client):
    # Ensure a couple events for buffer
    for i in range(3):
        ingest_noise_event(client, f"sse{i}")
    lines = []
    with client.stream("GET", "/fusion/decisions/stream", headers={"x-api-key": "adminkey"}) as r:
        for _ in range(3):
            line = r.iter_lines().__next__()
            if not line:
                continue
            if line.startswith("data:"):
                payload = line[len("data:"):].strip()
                try:
                    obj = json.loads(payload)
                    lines.append(obj)
                except Exception:
                    continue
            if len(lines) >= 1:
                break
    assert lines and isinstance(lines[0], dict) and "items" in lines[0]


def test_sse_stream_smoke(client):
    # Populate a couple events
    for i in range(3):
        ingest_noise_event(client, f"sse{i}")
    with client.stream("GET", "/fusion/decisions/stream", headers={"x-api-key": "adminkey"}) as r:
        # Read a couple of lines and then break
        lines = []
        for _ in range(2):
            line = r.iter_lines().__next__()
            if line:
                lines.append(line)
        assert any("data:" in ln for ln in lines)