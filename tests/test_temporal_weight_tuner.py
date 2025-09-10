from config import runtime_params
from core.detect.fusion import arbitrator
from core.detect.interface import registry
from core.pipeline import Pipeline
from core.event import Event

def test_temporal_weight_tuner_increase():
    # Enable strategy and tuner
    runtime_params.update_param('detection.fusion.strategy', 'weighted_sum', reason='test')
    runtime_params.update_param('fusion.temporal.tuner.enabled', True, reason='test')
    runtime_params.update_param('fusion.temporal.tuner.target_uplift', 1.0, reason='test')
    runtime_params.update_param('fusion.temporal.tuner.tolerance', 0.05, reason='test')
    runtime_params.update_param('fusion.temporal.tuner.cooldown_s', 1.0, reason='test')  # minimal cooldown for test
    runtime_params.update_param('detection.temporal.enable_transformer', True, reason='test')
    runtime_params.update_param('detection.temporal.simple_model', True, reason='test')
    runtime_params.update_param('detection.temporal.encoder', 'variance', reason='test')
    runtime_params.update_param('detection.temporal.var_threshold', 0.01, reason='test')  # minimum allowed threshold
    runtime_params.update_param('fusion.temporal.tuner.min_baseline', 1, reason='test')
    runtime_params.update_param('detection.temporal.weight', 0.0, reason='test')

    p = Pipeline(['tenant_wt'])
    arb = arbitrator()
    # Simulate baseline anomalies fewer than temporal to trigger increase
    # We'll inject a fake "baseline" anomaly manually in arbitrator fuse input after some events to ensure baseline count >0
    baseline_result = {'detector': 'baseline', 'tenant': 'tenant_wt', 'event_id': 'b1'}

    # Generate events to create temporal anomalies (variance needs window fill; assume window size from runtime_params or default 20)
    temporal_detector = registry.get('temporal')
    assert temporal_detector is not None
    import time
    for i in range(40):
        temporal_detector.process(Event(tenant_id='tenant_wt', features={'f': float(i)}))  # warm window
        temporal_anoms = temporal_detector.process(Event(tenant_id='tenant_wt', features={'f': float(i)+0.01}))  # trigger variance
        if 30 <= i <= 39:
            fused, _ = arb.fuse({'baseline': [baseline_result], 'temporal': temporal_anoms, 'snn': []})
            time.sleep(1.05)  # allow cooldown window
        else:
            fused, _ = arb.fuse({'baseline': [], 'temporal': temporal_anoms, 'snn': []})

    new_weight = runtime_params.get_param('detection.temporal.weight')
    assert new_weight is not None and new_weight > 0.0, 'Tuner should have increased temporal weight from 0'
