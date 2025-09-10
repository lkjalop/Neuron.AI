from scanner.neuromorphic.signal import compute_neuromorphic_signal

def test_neuromorphic_variance_mode():
    events = [
        {"id":1, "value":10},
        {"id":2, "value":200},
        {"id":3, "value":50},
        {"id":4, "value":300},
        {"id":5, "value":30},
    ]
    params = {"scanner.neuromorphic.mode": "variance", "scanner.neuromorphic.var_scale": 150.0}
    sig = compute_neuromorphic_signal(events, params)
    assert 0.0 <= sig <= 1.0
    # Expect some non-trivial variance => signal > 0
    assert sig > 0

def test_neuromorphic_spike_density_mode():
    events = [
        {"id":1, "spike_density": 0.2},
        {"id":2, "spike_density": 0.6},
        {"id":3, "spike_density": 0.8},
    ]
    params = {"scanner.neuromorphic.mode": "spike_density"}
    sig = compute_neuromorphic_signal(events, params)
    assert 0.0 <= sig <= 0.8
