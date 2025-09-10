import time
from prometheus_client import generate_latest


def test_governance_signal_and_metric(test_app, ensure_pipeline):
    # Use executive_agg to simulate fusion behavior
    from core.main import executive_agg

    # Induce a high composite regime
    for _ in range(10):
        executive_agg.record_fusion(overlap_ratio=0.05, snn_unique_ratio=0.4, suppression_rate=0.8)
        time.sleep(0.001)

    # API returns composite > 0
    r = test_app.get('/governance/signal')
    assert r.status_code == 200
    data = r.json()
    assert data.get('composite', 0.0) > 0.2

    # Metrics contain composite gauge
    blob = generate_latest().decode()
    assert 'neuron_governance_composite_signal' in blob

    # Flip to a lower composite regime and ensure it decreases
    for _ in range(10):
        executive_agg.record_fusion(overlap_ratio=0.9, snn_unique_ratio=0.05, suppression_rate=0.1)
        time.sleep(0.001)

    r2 = test_app.get('/governance/signal')
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2.get('composite', 1.0) < data.get('composite', 0.0)

    # Presence of state transitions metric family after regime change
    blob2 = generate_latest().decode()
    assert 'neuron_governance_composite_state_transitions_total' in blob2
