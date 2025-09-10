import math
import pytest
from config import runtime_params
from core.detect.fusion import arbitrator

# Minimal stub detection results

def make_result(detector: str, activity: float = 0.0, threshold: float = 1.0):
    return {
        "detector": detector,
        "activity": activity,
        "threshold": threshold,
        "tenant": "t0",
        "event_id": "e0",
    }

@pytest.fixture(autouse=True)
def reset_strategy():
    # Ensure strategy set to weighted_sum for each test
    runtime_params.update_param("detection.fusion.strategy", "weighted_sum", reason="test_setup")
    runtime_params.update_param("fusion.weight.baseline", 0.6, reason="test_setup")
    runtime_params.update_param("fusion.weight.snn", 0.4, reason="test_setup")
    runtime_params.update_param("fusion.weighted_sum.suppress_threshold", 0.0, reason="test_setup")
    yield


def test_weighted_sum_scoring_simple():
    arb = arbitrator()
    dets = {
        "baseline": [make_result("baseline")],
        "snn": [make_result("snn", activity=2.0, threshold=1.0)],
    }
    fused, meta = arb.fuse(dets)
    assert meta.get("strategy") == "weighted_sum"
    # Expect 2 fused (union) results
    assert len(fused) == 2
    # Find SNN fused record (activity 2, threshold 1 => snn_norm=(2-1)/(1*2)=0.5)
    snn_fused = [r for r in fused if r["detector"] == "snn"][0]
    expected_score = 0.6 * 1.0 + 0.4 * 0.5
    assert math.isclose(snn_fused["fusion_decision_score"], expected_score, rel_tol=1e-6)


def test_weighted_sum_suppression_applies():
    arb = arbitrator()
    # Baseline absent; SNN anomaly with low activity just above threshold -> small norm
    runtime_params.update_param("fusion.weighted_sum.suppress_threshold", 0.25, reason="test_suppress")
    dets = {
        "baseline": [],
        "snn": [make_result("snn", activity=1.05, threshold=1.0)],  # snn_norm ~ (0.05/2)=0.025
    }
    fused, meta = arb.fuse(dets)
    # Should suppress (no baseline, score ~ 0.4*0.025=0.01 < 0.25)
    assert len(fused) == 0
    assert meta.get("suppressed") == 1


def test_weighted_sum_no_suppression_when_baseline_present():
    arb = arbitrator()
    runtime_params.update_param("fusion.weighted_sum.suppress_threshold", 0.5, reason="test_no_sup")
    dets = {
        "baseline": [make_result("baseline")],
        "snn": [make_result("snn", activity=1.05, threshold=1.0)],
    }
    fused, meta = arb.fuse(dets)
    # Baseline present => baseline_present=1 so score >= w_b even if SNN norm tiny
    assert len(fused) == 2
    assert meta.get("suppressed") == 0


def test_weighted_sum_weight_defaults_guard():
    arb = arbitrator()
    # Set pathological weights (sum ~0) should fallback to 0.5/0.5 logic inside strategy
    runtime_params.update_param("fusion.weight.baseline", 0.0, reason="test_weights")
    runtime_params.update_param("fusion.weight.snn", 0.0, reason="test_weights")
    dets = {
        "baseline": [make_result("baseline")],
        "snn": [make_result("snn", activity=3.0, threshold=1.0)],
    }
    fused, meta = arb.fuse(dets)
    snn_fused = [r for r in fused if r["detector"] == "snn"][0]
    # norm=(3-1)/(1*2)=1 -> clipped to 1; fallback weights 0.5,0.5 => score=0.5*1 + 0.5*1 =1.0
    assert math.isclose(snn_fused["fusion_decision_score"], 1.0, rel_tol=1e-6)
