import time
import pytest
from fastapi.testclient import TestClient

from core.main import app, _MEMORY_PATTERNS  # type: ignore

client = TestClient(app)


def test_memory_pattern_ttl_and_eviction():
    # Add pattern with short TTL
    r = client.post('/memory/patterns', json={'pattern': 'alpha', 'ttl_s': 1})
    assert r.status_code == 200
    pid = r.json()['created']['id']
    # Confirm searchable immediately
    r = client.get('/memory/patterns')
    assert any(p['id'] == pid for p in r.json()['items'])
    # Wait past TTL and trigger prune via add
    time.sleep(1.2)
    client.post('/memory/patterns', json={'pattern': 'beta'})
    # TTL item should be gone (pruned)
    r = client.get('/memory/patterns')
    ids = {p['id'] for p in r.json()['items']}
    assert pid not in ids


def test_temporal_buffer_ingest_and_status():
    r = client.post('/temporal/buffer/ingest', json={'tenant': 't1', 'features': {'x': 1}})
    assert r.status_code == 200
    r = client.get('/temporal/buffer/status', params={'tenant': 't1'})
    assert r.status_code == 200
    data = r.json()['tenants']['t1']
    assert data['size'] >= 1
    assert 'ready' in data


def test_hunting_dsl_enhancements():
    from hunting.dsl import parse
    # equality wildcard
    q = parse('severity=H*')
    pred = q.predicates[0]
    rec = {'risk_severity': 'HIGH'}
    assert pred(rec)
    # NOT operator
    q2 = parse('NOT severity=LOW AND severity!=CRITICAL')
    assert all(p({'risk_severity': 'HIGH'}) for p in q2.predicates)
    # substring / glob ~
    q3 = parse('cve~CVE-2025*')
    assert q3.predicates[0]({'cve_id': 'CVE-2025-1234'})
