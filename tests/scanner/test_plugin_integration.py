from scanner.plugins.dummy_example import DummyExposurePlugin
from scanner.plugins.base import ScanContext


def test_dummy_plugin_generates_findings():
    plugin = DummyExposurePlugin()
    params = {"scanner.dummy.threshold": 100, "scanner.score.base_weight":1.0, "scanner.score.neuromorphic_weight":0.0, "scanner.score.scale":1.0, "_neu_signal":0.0}
    ctx = ScanContext(params=params, ontology_store={})
    events = [
        {"id":1, "value":50},
        {"id":2, "value":250},
        {"id":3, "value":180},
    ]
    findings = plugin.scan(events, ctx)
    # Expect two findings (250 & 180 > 100)
    assert len(findings) == 2
    sev_levels = {f.severity for f in findings}
    assert "MEDIUM" in sev_levels or "HIGH" in sev_levels
    # Ensure fingerprints assigned
    for f in findings:
        assert f.fingerprint is not None or f.compute_fingerprint()
