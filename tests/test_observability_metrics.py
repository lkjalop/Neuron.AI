import re, os, json, time
from fastapi.testclient import TestClient
from core.main import app

client = TestClient(app)

# Helper to fetch metrics text

def _metrics_text():
    r = client.get('/metrics')
    assert r.status_code == 200
    return r.text

def test_observability_new_metrics():
    # Exercise story endpoints
    create = client.post('/story', json={'content': 'hello world'})
    assert create.status_code in (200,201,204) or create.status_code == 200
    share_id = (create.json().get('story') or {}).get('share_id')
    if share_id:
        fetch = client.get(f'/story/{share_id}')
        assert fetch.status_code == 200
    prune = client.post('/story/prune')
    assert prune.status_code == 200
    # Exercise report endpoints (commit + integrity scan) using minimal payload
    commit = client.post('/report/commit', json={'content': 'r1'})
    # commit may require auth; ignore if unauthorized in minimalist mode
    if commit.status_code == 200:
        integ = client.post('/report/integrity/scan')
        assert integ.status_code in (200,401,403) or integ.status_code == 200
    # Fetch metrics
    text = _metrics_text()
    # Look for latency histograms (family headers) and gauges
    expected_patterns = [
        r'^story_endpoint_latency_seconds_bucket',
        r'^report_endpoint_latency_seconds_bucket',
        r'^story_file_size_bytes',
        r'^report_file_size_bytes',
        r'^story_last_prune_ts',
        r'^report_last_integrity_scan_ts',
        r'^runtime_param_value{',
    ]
    missing = []
    for pat in expected_patterns:
        if not re.search(pat, text, re.MULTILINE):
            missing.append(pat)
    assert not missing, f"Missing expected metric patterns: {missing}\nSample metrics tail:\n" + '\n'.join(text.splitlines()[-40:])
