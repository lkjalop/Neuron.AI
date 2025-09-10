import time
from core import metrics
from runtime.param_store import get_param, set_param

# Import tuner module functions
import importlib


def test_tuner_adjusts_weight(monkeypatch):
    tuner = importlib.import_module('scripts.run_tuner')
    # Speed up eligibility by setting cooldown negative
    monkeypatch.setenv('TUNER_COOLDOWN', '0')
    # Ensure registry has a DETECTOR_UNIQUE_RATIO sample
    # We can't directly push into the gauge without calling .set on labeled instance
    g = metrics.DETECTOR_UNIQUE_RATIO.labels(tenant='global', detector='baseline_stats')
    g.set(0.5)  # Above HI threshold (0.30) => increase
    key = 'fusion.weight.baseline_stats'
    set_param(key, 1.0, actor='test', reason='init')
    # Force update call directly (avoid loop)
    tuner._update('baseline_stats', unique_ratio=0.5, fp_rate=0.0)
    new_val = float(get_param(key))
    assert new_val > 1.0


def test_tuner_decreases_weight(monkeypatch):
    tuner = importlib.import_module('scripts.run_tuner')
    monkeypatch.setenv('TUNER_COOLDOWN', '0')
    g = metrics.DETECTOR_UNIQUE_RATIO.labels(tenant='global', detector='snn_detector')
    g.set(0.01)  # Below LO threshold (0.05) => decrease
    key = 'fusion.weight.snn_detector'
    set_param(key, 1.0, actor='test', reason='init')
    tuner._update('snn_detector', unique_ratio=0.01, fp_rate=0.0)
    new_val = float(get_param(key))
    assert new_val < 1.0
