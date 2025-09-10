from core.pipeline import Pipeline

def test_pipeline_has_maybe_register_snn():
    # Regression: ensure method not accidentally nested/removed
    assert hasattr(Pipeline, '_maybe_register_snn'), "Pipeline missing _maybe_register_snn (regression)"
