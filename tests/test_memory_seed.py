from fastapi.testclient import TestClient
from core.main import app, _record_memory_confirmation, _FUSION_DECISIONS
from core.detect.fusion import arbitrator
from config import runtime_params
import time

client = TestClient(app)


def test_memory_seed_and_uplift_gating(monkeypatch):
    # Monkeypatch get_param to return a seed value when asked for fusion.memory.signal.seed
    original_get = runtime_params.get_param
    def fake_get(key):  # type: ignore
        if key == 'fusion.memory.signal.seed':
            return 0.2
        return original_get(key)
    monkeypatch.setattr(runtime_params, 'get_param', fake_get)
    # Clear memory weight if present
    try:
        runtime_params.update_param('fusion.weight.memory_signal', None, reason='clear', actor='test')  # type: ignore[attr-defined]
    except Exception:
        pass
    # Set uplift threshold high so initial ratio (0) doesn't apply multiplier
    runtime_params.update_param('fusion.memory.uplift.threshold', 0.5, reason='test_thr', actor='test')  # type: ignore[attr-defined]
    # Prepare temporal anomaly with HIGH band so temporal path considered
    a = arbitrator()
    # Simulate baseline anomaly so fusion has context
    baseline_anom = {'id': 'b1', 'tenant': 't1'}
    temporal_anom = {'id': 't1a', 'tenant': 't1', 'confidence_band': 'HIGH', 'score': 0.9}
    fused, meta = a._weighted_sum({'baseline': [baseline_anom], 'temporal': [temporal_anom]})  # type: ignore
    # Find temporal fused record
    rec = None
    for r in fused:
        if r.get('id') == 't1a':
            rec = r
            break
    assert rec is not None
    weights = rec['fusion_components']['weights']
    # Memory weight may not appear until temporal contribution path executes with effective weight >0
    # Capture initial score
    score_no_confirm = rec['fusion_decision_score']
    # Now lower threshold and simulate memory confirmations to raise verified ratio
    runtime_params.update_param('fusion.memory.uplift.threshold', 0.0, reason='lower_thr', actor='test')  # type: ignore[attr-defined]
    # Add fusion decision record for ratio denominator
    _FUSION_DECISIONS.append({'id': 'tempDecision', 'tenant': 't1', 'ts': time.time()})
    _record_memory_confirmation('tempDecision', 't1', 'baseline')
    fused2, _ = a._weighted_sum({'baseline': [baseline_anom], 'temporal': [temporal_anom]})  # type: ignore
    rec2 = None
    for r in fused2:
        if r.get('id') == 't1a':
            rec2 = r
            break
    assert rec2 is not None
    score_with_confirm = rec2['fusion_decision_score']
    # Expect score with confirmation (memory multiplier active) >= prior score
    assert score_with_confirm >= score_no_confirm
