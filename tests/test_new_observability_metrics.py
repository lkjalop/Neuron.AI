import re
import time
import json
from fastapi.testclient import TestClient
from core.main import app, pipeline
from core import metrics

# Helper to fetch raw metrics text

def scrape_metrics(client: TestClient) -> str:
    resp = client.get('/metrics')
    assert resp.status_code == 200
    return resp.text


def find_metric_sample(metrics_text: str, metric_name: str) -> bool:
    return any(line.startswith(metric_name) for line in metrics_text.splitlines())


def test_temporal_buffer_retained_ratio_and_ready(client: TestClient | None = None):
    c = client or TestClient(app)
    # Ingest enough to exceed readiness threshold (default 25)
    for i in range(30):
        payload = {"tenant": "tenant_obsv", "features": {"f": i}}
        r = c.post('/temporal/buffer/ingest', json=payload)
        assert r.status_code == 200
    text = scrape_metrics(c)
    assert find_metric_sample(text, 'neuron_temporal_buffer_ready'), 'temporal buffer ready gauge missing'
    assert find_metric_sample(text, 'neuron_temporal_buffer_retained_ratio'), 'retained ratio gauge missing'


def test_strategy_fallback_latency_metric(client: TestClient | None = None):
    c = client or TestClient(app)
    assert pipeline is not None
    ok = pipeline._test_trigger_strategy_fallback('tenant_fb')  # type: ignore[attr-defined]
    assert ok, 'fallback test helper failed'
    text = scrape_metrics(c)
    # Expect a sample with tenant label
    assert 'neuron_fusion_strategy_fallback_latency_seconds_bucket' in text
    assert 'tenant="tenant_fb"' in text


def test_memory_signal_gating_latency_metric(client: TestClient | None = None):
    c = client or TestClient(app)
    assert pipeline is not None
    ok = pipeline._test_trigger_memory_gating('tenant_mem')  # type: ignore[attr-defined]
    assert ok, 'memory gating helper failed'
    text = scrape_metrics(c)
    assert 'neuron_memory_signal_gating_latency_seconds_bucket' in text


def test_drift_guard_trace_endpoint_and_persist(tmp_path):
    # Enable persistence via runtime param monkeypatch if available
    from config import runtime_params
    runtime_params.update_param('governance.drift_guard.trace.persist', True, reason='test', actor='test')
    c = TestClient(app)
    assert pipeline is not None
    # Force multiple drift guard evaluations
    for _ in range(3):
        pipeline._maybe_drift_guard('tenant_trace', suppression_rate=0.95, force=True)  # type: ignore[attr-defined]
    resp = c.get('/governance/drift/trace', params={'tenant': 'tenant_trace', 'limit': 10})
    assert resp.status_code == 200
    data = resp.json()
    assert data['count'] >= 1
    # Check JSONL file existence
    import os
    path = 'artifacts/governance/drift_guard_traces.jsonl'
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            lines = [ln.strip() for ln in f if ln.strip()]
            assert lines, 'expected persisted trace lines'
            rec = json.loads(lines[-1])
            assert rec.get('tenant') == 'tenant_trace'


# Pytest fixture fallback if not provided externally
try:
    import pytest  # noqa: F401
except Exception:
    pass
