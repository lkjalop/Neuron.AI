import time
from core.governance_ext.diminishing import DiminishingReturnsMonitor
from config import runtime_params as rp_mod

class DummyParams:
    def __init__(self):
        self.data = {}
    def get(self, k):
        return self.data.get(k)
    def set(self, k, v):
        self.data[k] = v

# Inject dummy runtime params if module expects global runtime_params

def test_plateau_triggers_hopfield_disable(monkeypatch):
    dummy = DummyParams()
    dummy.data.update({
        # Set higher threshold so tiny drift counts as plateau
        "governance.hopfield.plateau.delta_threshold": 0.001,
        "governance.hopfield.plateau.window_min": 5,
        "governance.hopfield.plateau.cooldown_s": 0,
    })
    # Patch get_param & update_param directly
    def fake_get_param(key):
        return dummy.get(key)
    def fake_update_param(key, value, reason=None, actor=None):
        dummy.set(key, value)
    monkeypatch.setattr("config.runtime_params.get_param", fake_get_param, raising=False)
    monkeypatch.setattr("config.runtime_params.update_param", fake_update_param, raising=False)
    mon = DiminishingReturnsMonitor()
    # Feed nearly flat values
    for v in [0.1000,0.10010,0.10005,0.10007,0.10008,0.10009]:
        mon._snn_unique_hist.append((time.time(), v))
    # Invoke plateau check manually with last value
    mon._maybe_plateau(0.10009)
    assert dummy.get("hopfield.enabled") is False, "Hopfield not disabled after plateau detection"
