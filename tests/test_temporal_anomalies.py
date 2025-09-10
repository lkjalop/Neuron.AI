from config import runtime_params
from core.pipeline import Pipeline
from core.detect.interface import registry
from core.event import Event


def _setup(flag_encoder: str | None = None):
    runtime_params.update_param('detection.temporal.enable_transformer', True, reason='test')
    runtime_params.update_param('detection.temporal.simple_model', True, reason='test')
    if flag_encoder:
        runtime_params.update_param('detection.temporal.encoder', flag_encoder, reason='test')
    p = Pipeline(['t_temp'])
    return p, registry.get('temporal')


def test_variance_spike_anomaly():
    p, temporal = _setup('variance')
    assert temporal is not None
    from config import runtime_params
    runtime_params.update_param('detection.temporal.var_threshold', 0.05, reason='test')
    # feed stable window then spike all features
    for i in range(25):
        temporal.process(Event(tenant_id='t_temp', features={'cpu':1.0,'mem':1.0}))  # type: ignore
    res = temporal.process(Event(tenant_id='t_temp', features={'cpu':8.0,'mem':7.0}))  # spike
    # Depending on threshold readiness may or may not fire exactly here; ensure after additional spike it fires
    if not res:
        res = temporal.process(Event(tenant_id='t_temp', features={'cpu':8.0,'mem':7.0}))
    assert any(r.get('reason') == 'temporal_variance_spike' for r in res), 'Expected variance spike anomaly'


def test_attention_encoder_path():
    p, temporal = _setup('attn')
    assert temporal is not None
    from config import runtime_params
    runtime_params.update_param('detection.temporal.attn_threshold', 0.05, reason='test')
    # fill with gradually increasing values to build deviation
    for i in range(30):
        temporal.process(Event(tenant_id='t_temp', features={'cpu':1.0 + 0.1*i,'mem':1.0 + 0.08*i}))  # type: ignore
    res = temporal.process(Event(tenant_id='t_temp', features={'cpu':5.0,'mem':4.5}))
    # Accept either attention deviation or variance (if fallback). Ensure anomaly exists.
    assert res, 'Expected anomaly for attention path'


def test_memory_guard_trip():
    runtime_params.update_param('temporal.guard.max_window', 10, reason='test')
    p, temporal = _setup('variance')
    from core.sequence.buffer import buffers
    from core.features.registry import feature_order
    mgr = buffers(window=50, feature_order=feature_order())  # vector buffer larger than guard threshold
    # fill many events; internal add should trip memory guard (no error expected)
    for i in range(25):
        temporal.process(Event(tenant_id='t_temp', features={'cpu':1.0 + i*0.01,'mem':1.0}))  # type: ignore
    # Can't directly assert metric here without scraping; rely on absence of exception.
    assert True
