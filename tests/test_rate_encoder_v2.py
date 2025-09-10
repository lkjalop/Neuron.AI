import time
from core.detect.snn import RateEncoderV2

def test_rate_encoder_v2_burst_vs_constant():
    enc = RateEncoderV2(window=30, rate_scale=1.0, burst_k=2.5, burst_boost=2.0, density_cap=0.5)
    # Two features: one constant moderate, one large burst
    feats = {"const": 5.0, "burst": 200.0}
    keys, spikes = enc.encode(feats)
    assert set(keys) == {"burst", "const"}
    # Count spikes per feature
    idx = {k: i for i, k in enumerate(keys)}
    burst_spikes = sum(row[idx["burst"]] for row in spikes)
    const_spikes = sum(row[idx["const"]] for row in spikes)
    # Expect burst feature to have >= const spikes (with boost) but density cap prevents runaway
    assert burst_spikes >= const_spikes, f"expected burst >= const spikes; burst={burst_spikes} const={const_spikes}"
    total = burst_spikes + const_spikes
    max_allowed = int(0.5 * 30 * 2 + 1)  # density cap + cushion
    assert total <= max_allowed, f"density cap exceeded total={total} max={max_allowed}"
