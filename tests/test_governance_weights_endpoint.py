import json
import types


def test_governance_weights_endpoint_import_and_call(monkeypatch):
    """Basic import and smoke test for /governance/weights handler.

    We call the function directly to avoid needing the ASGI test client wiring in this repo snapshot.
    Asserts shape and types; tolerant to missing audit logs.
    """
    # Import module
    import importlib
    mod = importlib.import_module('core.main')
    assert hasattr(mod, 'governance_weights')

    # Ensure executive_agg exists with required attributes for band call
    assert hasattr(mod, 'executive_agg')

    # Call the function directly
    res = mod.governance_weights()  # default limit
    assert isinstance(res, dict)
    assert 'weights' in res and isinstance(res['weights'], dict)
    w = res['weights']
    # required keys
    for k in ['temporal', 'transformer', 'baseline', 'snn', 'iforest', 'temporal_enabled', 'transformer_enabled', 'shadow_mode']:
        assert k in w
    # numeric types for weights
    for k in ['temporal', 'transformer', 'baseline', 'snn', 'iforest']:
        assert isinstance(w[k], (int, float))

    assert 'governance_composite' in res and isinstance(res['governance_composite'], dict)
    comp = res['governance_composite']
    # Required composite fields
    for k in ['current', 'band', 'thresholds', 'hysteresis']:
        assert k in comp
    th = comp['thresholds']
    assert isinstance(th, dict)
    for k in ['low', 'medium', 'high']:
        assert k in th

    assert 'audit' in res and isinstance(res['audit'], dict)
    a = res['audit']
    # logs may be empty but must be present
    assert 'temporal_adjust_log' in a and isinstance(a['temporal_adjust_log'], list)
    assert 'param_changes' in a and isinstance(a['param_changes'], list)
