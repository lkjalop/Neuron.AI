import math
import pytest

from config import runtime_params
from core.detect.snn import RateEncoderV2


def make_features(n: int, base: float, spike: float):
    # Construct n features; one very large to push projected density high
    feats = {f"f{i}": base for i in range(n)}
    feats["hot"] = spike
    return feats


def project_density(rates, T, F):
    # Expected density approximation (sum rates / F)
    expected_spikes = sum(r * T for r in rates)
    return expected_spikes / (T * F)


def test_density_cap_scales_rates():
    T = 20
    n_feats = 10
    encoder = RateEncoderV2(window=T, rate_scale=5.0, density_cap=0.10)
    # Configure runtime shrink & floor to minimize interference
    runtime_params.update_param("snn.encoder.rate_v2.global_shrink", 1.0, reason="density_cap_test")
    runtime_params.update_param("snn.encoder.rate_v2.min_floor", 0.0, reason="density_cap_test")
    feats = make_features(n_feats, base=10.0, spike=500.0)
    keys, spikes = encoder.encode(feats)
    # Re-run with cap disabled to infer uncapped density by temporarily patching attribute
    uncapped_encoder = RateEncoderV2(window=T, rate_scale=5.0, density_cap=1.0)
    runtime_params.update_param("snn.encoder.rate_v2.global_shrink", 1.0, reason="density_cap_test")
    runtime_params.update_param("snn.encoder.rate_v2.min_floor", 0.0, reason="density_cap_test")
    keys2, spikes_uncapped = uncapped_encoder.encode(feats)
    assert keys == keys2
    # Compute achieved densities
    spike_count_capped = sum(sum(row) for row in spikes)
    spike_count_uncapped = sum(sum(row) for row in spikes_uncapped)
    F = len(keys)
    density_capped = spike_count_capped / (T * F)
    density_uncapped = spike_count_uncapped / (T * F)
    # Uncapped should exceed target; capped should be <= density_cap * 1.05 (5% tolerance)
    assert density_uncapped > 0.10, "Uncapped density unexpectedly low; test ineffective"
    assert density_capped <= 0.105, f"Density cap not enforced (got {density_capped})"
    # Ensure scaling actually reduced spikes
    assert spike_count_capped < spike_count_uncapped, "Density cap did not reduce spike count"


def test_density_cap_no_action_when_below():
    T = 20
    encoder = RateEncoderV2(window=T, rate_scale=1.0, density_cap=0.50)
    runtime_params.update_param("snn.encoder.rate_v2.global_shrink", 0.2, reason="density_cap_test")
    runtime_params.update_param("snn.encoder.rate_v2.min_floor", 0.0, reason="density_cap_test")
    feats = {"a": 0.5, "b": 0.2, "c": 0.1}
    keys, spikes = encoder.encode(feats)
    spike_count = sum(sum(row) for row in spikes)
    F = len(keys)
    density = spike_count / (T * F)
    # Below cap: with small values density should be modest
    assert density < 0.50
