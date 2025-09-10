import time
import types

import pytest

from config import runtime_params
from core.detect.fusion import FusionArbitrator


@pytest.fixture(autouse=True)
def _reset_params():
    # Ensure common tuner configuration for all tests
    runtime_params.update_param('detection.fusion.strategy', 'weighted_sum', reason='test')
    runtime_params.update_param('fusion.temporal.tuner.enabled', True, reason='test')
    runtime_params.update_param('fusion.temporal.tuner.target_uplift', 1.0, reason='test')
    runtime_params.update_param('fusion.temporal.tuner.tolerance', 0.1, reason='test')
    runtime_params.update_param('fusion.temporal.tuner.hysteresis', 0.05, reason='test')
    runtime_params.update_param('fusion.temporal.tuner.cooldown_s', 60.0, reason='test')
    runtime_params.update_param('fusion.temporal.tuner.min_baseline', 3, reason='test')
    runtime_params.update_param('fusion.temporal.tuner.min_anomalies', 10, reason='test')
    runtime_params.update_param('fusion.temporal.tuner.max_step', 0.25, reason='test')
    runtime_params.update_param('fusion.temporal.tuner.max_abs_delta', 0.3, reason='test')
    runtime_params.update_param('fusion.temporal.tuner.min_weight', 0.0, reason='test')
    runtime_params.update_param('fusion.temporal.tuner.max_weight', 2.0, reason='test')
    runtime_params.update_param('fusion.temporal.tuner.seed_weight', 0.05, reason='test')
    # Start from a non-zero weight to exercise proportional delta when needed
    runtime_params.update_param('detection.temporal.weight', 0.1, reason='test')
    yield


def _spy_update(monkeypatch):
    calls = []
    def _recorder(key, value, reason, actor='system'):
        calls.append((key, value, reason, actor))
        return value
    monkeypatch.setattr(runtime_params, 'update_param', _recorder, raising=True)
    return calls


def test_tuner_cooldown_respected(monkeypatch):
    arb = FusionArbitrator()
    # Force cooldown active by setting last_ts to now and cooldown to large
    arb._tuner_last_ts = time.time()
    runtime_params.update_param('fusion.temporal.tuner.cooldown_s', 300.0, reason='test')
    calls = _spy_update(monkeypatch)
    # Provide values that would otherwise be far below band to trigger increase
    arb._maybe_tune_temporal_weight(baseline_count=100, temporal_applied=10)
    assert len(calls) == 0, 'No adjustments should occur during cooldown'


def test_tuner_min_baseline_gating(monkeypatch):
    arb = FusionArbitrator()
    # Ensure cooldown passed
    arb._tuner_last_ts = time.time() - 1000
    # Set min_baseline higher than provided baseline
    runtime_params.update_param('fusion.temporal.tuner.min_baseline', 50, reason='test')
    calls = _spy_update(monkeypatch)
    arb._tuner_window.clear()
    # After append, total_baseline will be 25 (< 50)
    arb._maybe_tune_temporal_weight(baseline_count=25, temporal_applied=40)
    assert len(calls) == 0, 'No adjustments when total_baseline below min_baseline'


def test_tuner_min_anomalies_gating(monkeypatch):
    arb = FusionArbitrator()
    arb._tuner_last_ts = time.time() - 1000
    # Min baseline satisfied, but min_anomalies very high
    runtime_params.update_param('fusion.temporal.tuner.min_baseline', 3, reason='test')
    runtime_params.update_param('fusion.temporal.tuner.min_anomalies', 200, reason='test')
    calls = _spy_update(monkeypatch)
    arb._tuner_window.clear()
    # Baseline high enough, but temporal total after append will be < 200
    arb._maybe_tune_temporal_weight(baseline_count=120, temporal_applied=30)
    assert len(calls) == 0, 'No adjustments when total_temporal below min_anomalies'


def test_tuner_hysteresis_band_behavior(monkeypatch):
    arb = FusionArbitrator()
    arb._tuner_last_ts = time.time() - 1000
    # Configure a tight band: target=1.0, tol=0.1, hysteresis=0.05 -> band [0.85, 1.15]
    runtime_params.update_param('fusion.temporal.tuner.target_uplift', 1.0, reason='test')
    runtime_params.update_param('fusion.temporal.tuner.tolerance', 0.1, reason='test')
    runtime_params.update_param('fusion.temporal.tuner.hysteresis', 0.05, reason='test')
    runtime_params.update_param('fusion.temporal.tuner.min_baseline', 10, reason='test')
    runtime_params.update_param('fusion.temporal.tuner.min_anomalies', 10, reason='test')
    # Case 1: within band -> no adjust
    calls = _spy_update(monkeypatch)
    arb._tuner_window.clear()
    # total_temporal / total_baseline = 95/100 = 0.95 (inside [0.85, 1.15])
    arb._tuner_window.append((100, 95))
    arb._maybe_tune_temporal_weight(baseline_count=0, temporal_applied=0)
    assert len(calls) == 0, 'No adjustments within hysteresis band'
    # Case 2: below lower bound -> adjust increase
    arb._tuner_last_ts = time.time() - 1000
    calls2 = _spy_update(monkeypatch)
    arb._tuner_window.clear()
    arb._tuner_window.append((100, 30))  # uplift=0.3 < 0.85
    arb._maybe_tune_temporal_weight(baseline_count=0, temporal_applied=0)
    assert len(calls2) == 1, 'Adjustment expected when uplift below lower bound'
    key, value, reason, actor = calls2[0]
    assert key == 'detection.temporal.weight'
    assert 'tuner_' in reason
    # Case 3: above upper bound -> adjust decrease
    arb._tuner_last_ts = time.time() - 1000
    calls3 = _spy_update(monkeypatch)
    arb._tuner_window.clear()
    arb._tuner_window.append((100, 200))  # uplift=2.0 > 1.15
    arb._maybe_tune_temporal_weight(baseline_count=0, temporal_applied=0)
    assert len(calls3) == 1, 'Adjustment expected when uplift above upper bound'
    key3, value3, reason3, actor3 = calls3[0]
    assert key3 == 'detection.temporal.weight'
    assert 'tuner_decrease' in reason3
