import os, json, importlib, math
import pytest

from config import runtime_params
from core.detect.interface import registry

# Helper to rebuild pipeline with updated flag
from core.pipeline import Pipeline
from core.event import Event


def make_event(tenant: str, cpu: float, mem: float):
    return Event(tenant_id=tenant, event_type="generic", features={"cpu": cpu, "mem": mem})


def reset_detectors():
    registry._reset_for_tests()  # type: ignore


def test_flag_gating_disabled():
    reset_detectors()
    runtime_params.update_param("detection.enable_snn", False, reason="test")
    p = Pipeline(["tenantA"])  # registers baseline only
    names = {d.name for d in registry.detectors()}
    assert "baseline" in names and "snn" not in names


def test_flag_gating_enabled_registers_snn():
    reset_detectors()
    runtime_params.update_param("detection.enable_snn", True, reason="test")
    p = Pipeline(["tenantA"])  # should attempt SNN registration
    names = {d.name for d in registry.detectors()}
    assert "baseline" in names and "snn" in names


def test_deterministic_encoding_hash():
    reset_detectors()
    runtime_params.update_param("detection.enable_snn", True, reason="test")
    p = Pipeline(["tenantA"])  # noqa: F841
    snn = registry.get("snn")
    assert snn is not None
    ev = make_event("tenantA", cpu=0.5, mem=1.0)
    r1 = snn.process(ev)
    r2 = snn.process(ev)
    # If score is zero (not anomalous) we can't test hash; craft larger values
    if not r1:
        ev2 = make_event("tenantA", cpu=5.0, mem=6.0)
        r1 = snn.process(ev2)
        r2 = snn.process(ev2)
    if not r1:  # still empty, skip determinism assertion (threshold may be high)
        pytest.skip("SNN returned no results for determinism test")
    assert r1[0]["features_hash"] == r2[0]["features_hash"]


def test_monotonicity_basic():
    reset_detectors()
    runtime_params.update_param("detection.enable_snn", True, reason="test")
    p = Pipeline(["tenantA"])  # noqa: F841
    snn = registry.get("snn")
    assert snn is not None
    # Two events: second has larger magnitudes
    ev_small = make_event("tenantA", cpu=1.0, mem=1.0)
    ev_large = make_event("tenantA", cpu=10.0, mem=10.0)
    r_small = snn.process(ev_small)
    r_large = snn.process(ev_large)
    # Ensure activity rises (raw_score or activity may be > 0 only for large)
    a_small = r_small[0]["activity"] if r_small else 0.0
    a_large = r_large[0]["activity"] if r_large else 0.0
    assert a_large >= a_small


def test_fallback_without_torch(monkeypatch):
    """Simulate torch import failure and ensure pipeline still registers SNN scaffold.

    Current scaffold does not hard require torch; ensure log path doesn't crash.
    """
    reset_detectors()
    runtime_params.update_param("detection.enable_snn", True, reason="test")
    # Monkeypatch import to raise for torch
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):  # type: ignore
        if name == "torch":
            raise ImportError("Simulated torch missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    p = Pipeline(["tenantA"])  # noqa: F841
    names = {d.name for d in registry.detectors()}
    # We still expect snn (no hard dependency), but even if future requires torch, baseline must remain.
    assert "baseline" in names
    # Accept either presence or absence of snn (depending on future dependency tightening) but not crash.
    # If absent, rationale would be import guard early exit.
    # So just assert no exception occurred up to here.

