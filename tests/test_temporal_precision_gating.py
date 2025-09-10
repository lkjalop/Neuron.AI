from config import runtime_params
from core.detect.fusion import arbitrator
from core import metrics

def test_temporal_precision_gating():
    # Configure fusion + temporal with small window for fast readiness
    runtime_params.update_param('detection.fusion.strategy', 'weighted_sum', reason='test')
    runtime_params.update_param('detection.temporal.enable_transformer', True, reason='test')
    runtime_params.update_param('detection.temporal.simple_model', True, reason='test')
    runtime_params.update_param('detection.temporal.encoder', 'variance', reason='test')
    runtime_params.update_param('snn.encoding_window', 5, reason='test')
    runtime_params.update_param('detection.temporal.var_threshold', 0.01, reason='test')
    runtime_params.update_param('fusion.temporal.precision_max_rate', 0.05, reason='test')
    runtime_params.update_param('detection.temporal.weight', 0.4, reason='test')

    arb = arbitrator()
    # Craft synthetic temporal anomaly record (as produced by temporal detector) with HIGH confidence
    synthetic_anom = [{
        'detector': 'temporal',
        'tenant': 'tenant_pg',
        'event_id': 'e1',
        'reason': 'temporal_variance_spike',
        'score': 0.7,
        'confidence_band': 'HIGH',
    }]
    # Force precision proxy rate above threshold so gating sets temporal_gated
    metrics.PRECISION_PROXY_RATE.labels(tenant='tenant_pg', detector='temporal').set(0.5)  # type: ignore[attr-defined]
    fused, _ = arb.fuse({'baseline': [], 'snn': [], 'temporal': synthetic_anom})
    gated = [r for r in fused if (r.get('fusion_components') or {}).get('temporal_gated')]
    assert gated, 'Expected at least one temporal anomaly gated due to precision rate limit'
