import pytest

from core.detect.fusion import arbitrator
from config import runtime_params


def test_temporal_transformer_gating_no_flags():
    # Ensure flags off
    runtime_params.update_param("detection.temporal.enabled", False, reason="test", actor="test")
    runtime_params.update_param("detection.transformer.enabled", False, reason="test", actor="test")
    runtime_params.update_param("fusion.weight.transformer", 1.0, reason="test", actor="test")
    arb = arbitrator()
    res, meta = arb.fuse({
        "baseline": [{"tenant":"t1"}],
        "temporal": [{"tenant":"t1","confidence_band":"HIGH","score":0.9}],
    })
    # With flags off, temporal should contribute 0 and transformer disabled
    assert any(r.get("fusion_components", {}).get("temporal") == 0.0 for r in res)


def test_transformer_weight_applied_when_enabled(monkeypatch):
    runtime_params.update_param("detection.transformer.enabled", True, reason="test", actor="test")
    runtime_params.update_param("fusion.weight.transformer", 0.7, reason="test", actor="test")
    # Patch transformer deviation to fixed value
    import core.temporal.transformer as t
    class _MockTT:
        def deviation(self):
            return 0.5
    monkeypatch.setattr(t, "instance", lambda: _MockTT())
    arb = arbitrator()
    res, meta = arb.fuse({"baseline": [{"tenant":"t1"}]})
    found = False
    for r in res:
        comp = r.get("fusion_components", {})
        if "transformer" in comp:
            assert comp["transformer"] == 0.5
            found = True
    assert found