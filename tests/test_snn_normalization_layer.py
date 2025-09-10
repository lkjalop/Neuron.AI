import math
from core.detect.snn_norm import normalizer
from config import runtime_params


def test_snn_normalization_bounds_after_warmup():
    runtime_params.update_param("snn.norm.enable", True, reason="norm_test", actor="test")
    runtime_params.update_param("snn.norm.window", 100, reason="norm_test", actor="test")
    runtime_params.update_param("snn.norm.min_samples", 30, reason="norm_test", actor="test")
    n = normalizer()
    tenant = "tnorm"
    # Feed increasing raw scores to build mapping
    for i in range(60):
        n.normalize(i * 0.5, tenant)  # raw feed
    # After warmup mapping should be applied
    mapped_values = [n.normalize(x * 0.5, tenant) for x in range(60, 70)]
    for v in mapped_values:
        assert 0.0 <= v <= 1.0 + 1e-6
    # Monotonic non-decreasing expectation (piecewise linear) for ascending inputs
    assert all(mapped_values[i] <= mapped_values[i+1] + 1e-6 for i in range(len(mapped_values)-1))


def test_snn_normalization_pre_warmup_passthrough():
    runtime_params.update_param("snn.norm.enable", True, reason="norm_test2", actor="test")
    runtime_params.update_param("snn.norm.window", 50, reason="norm_test2", actor="test")
    runtime_params.update_param("snn.norm.min_samples", 40, reason="norm_test2", actor="test")
    n = normalizer()
    tenant = "tnorm2"
    # Provide fewer than min_samples
    raw_scores = [0.2 * i for i in range(10)]
    outputs = [n.normalize(s, tenant) for s in raw_scores]
    # Expect outputs close to raw (within tolerance) because mapping not yet computed
    for inp, out in zip(raw_scores, outputs):
        assert math.isclose(inp, out, rel_tol=0.05, abs_tol=0.05), f"Expected passthrough pre-warmup inp={inp} out={out}"

