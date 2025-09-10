import math
import pytest
from config import runtime_params
from core.detect.fusion import arbitrator


def make_result(detector: str, **extra):
    base = {
        "detector": detector,
        "tenant": "t0",
        "event_id": "e0",
    }
    base.update(extra)
    return base


@pytest.fixture(autouse=True)
def setup_weighted_sum():
    runtime_params.update_param("detection.fusion.strategy", "weighted_sum", reason="test_setup")
    runtime_params.update_param("fusion.weight.baseline", 0.5, reason="test_setup")
    runtime_params.update_param("fusion.weight.snn", 0.25, reason="test_setup")
    runtime_params.update_param("detection.temporal.weight", 0.25, reason="test_setup")
    runtime_params.update_param("fusion.weighted_sum.suppress_threshold", 0.0, reason="test_setup")
    yield


def test_temporal_weight_applied_only_high_band():
    arb = arbitrator()
    # Temporal anomaly with HIGH band should contribute weight * score (score already 0..1)
    temporal_score = 0.8
    dets = {
        "temporal": [make_result("temporal", score=temporal_score, confidence_band="HIGH")],
    }
    fused, meta = arb.fuse(dets)
    assert meta.get("strategy") == "weighted_sum"
    assert meta.get("temporal_applied") == 1
    rec = fused[0]
    comp = rec["fusion_components"]
    assert not comp.get("temporal_gated")
    # baseline_present=0, snn_norm=0 -> decision score should be w_t * temporal_score
    expected = 0.25 * temporal_score
    assert math.isclose(rec["fusion_decision_score"], expected, rel_tol=1e-6)


def test_temporal_low_band_zero_influence():
    arb = arbitrator()
    dets = {
        "temporal": [make_result("temporal", score=0.9, confidence_band="LOW")],
    }
    fused, meta = arb.fuse(dets)
    rec = fused[0]
    comp = rec["fusion_components"]
    assert comp.get("temporal_gated") is True
    # Even though score is high, gating should zero influence (decision score = raw score passthrough, but no additive weights)
    # We treat fusion_decision_score as raw anomaly score when gated (no baseline/snn contributions)
    assert rec["fusion_decision_score"] == rec["score"]
    assert meta.get("temporal_applied") == 0


def test_temporal_weight_zero_disables_influence():
    runtime_params.update_param("detection.temporal.weight", 0.0, reason="disable_temporal")
    arb = arbitrator()
    dets = {
        "temporal": [make_result("temporal", score=0.7, confidence_band="CRITICAL")],
    }
    fused, meta = arb.fuse(dets)
    rec = fused[0]
    comp = rec["fusion_components"]
    assert comp.get("temporal_gated") is True  # treated as gated due to zero weight
    # Score should remain raw (no weighting influence)
    assert math.isclose(rec["fusion_decision_score"], 0.7, rel_tol=1e-6)
    assert meta.get("temporal_applied") == 0


def test_temporal_with_baseline_and_snn():
    arb = arbitrator()
    # Include baseline + snn + high confidence temporal
    dets = {
        "baseline": [make_result("baseline")],
        "snn": [make_result("snn", activity=2.0, threshold=1.0)],  # snn_norm=0.5 * w_s(0.25) -> 0.125 additive to baseline portion (0.5)
        "temporal": [make_result("temporal", score=0.6, confidence_band="HIGH")],
    }
    fused, meta = arb.fuse(dets)
    # Expect three fused entries
    assert len(fused) == 3
    # Find temporal record
    trec = [r for r in fused if r["detector"] == "temporal"][0]
    # For temporal record: baseline_present=1 -> baseline contribution 0.5, snn_norm excluded (0), temporal contribution 0.25 * 0.6 =0.15
    expected = 0.5 + 0.15
    assert math.isclose(trec["fusion_decision_score"], expected, rel_tol=1e-6)
    assert meta.get("temporal_applied") == 1
