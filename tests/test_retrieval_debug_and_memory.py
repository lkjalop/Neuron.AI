import re
import time
from fastapi.testclient import TestClient

from src.core.main import app, metrics, _run_retrieval_probe_once  # type: ignore

client = TestClient(app)


def _get_metric_value(family_name: str, labels: dict | None = None):
    # Scrape metrics endpoint and parse simple counter sample
    resp = client.get('/metrics')
    assert resp.status_code == 200
    target_lines = [l for l in resp.text.splitlines() if l.startswith(family_name)]
    if labels:
        # Build label matcher subset
        wanted = sorted([f'{k}="{v}"' for k,v in labels.items()])
        for line in target_lines:
            if all(s in line for s in wanted):
                m = re.search(r' (\d+(?:\.\d+)?)$', line)
                if m:
                    return float(m.group(1))
        return 0.0
    # aggregate sum (first sample without labels)
    total = 0.0
    for line in target_lines:
        m = re.search(r' (\d+(?:\.\d+)?)$', line)
        if m:
            total += float(m.group(1))
    return total


def test_retrieval_cache_hit_miss_and_ranking_debug():
    q = {"query": "test retrieval debug"}
    # Initial call -> expect cache miss counter inc after embedding stage
    before_miss = _get_metric_value('neuron_rag_embedding_cache_misses_total')
    before_hit = _get_metric_value('neuron_rag_embedding_cache_hits_total')
    r1 = client.post('/retrieval/pipeline', json=q)
    assert r1.status_code == 200
    after_miss = _get_metric_value('neuron_rag_embedding_cache_misses_total')
    assert after_miss >= before_miss + 1  # at least one miss
    # Second identical query should yield a hit
    r2 = client.post('/retrieval/pipeline', json=q)
    assert r2.status_code == 200
    after_hit = _get_metric_value('neuron_rag_embedding_cache_hits_total')
    assert after_hit >= before_hit + 1
    # Ranking debug endpoint returns items
    dbg = client.get('/retrieval/rank/debug?limit=5')
    assert dbg.status_code == 200
    data = dbg.json()
    assert 'items' in data and isinstance(data['items'], list)
    assert data['count'] == len(data['items'])
    # RAG_RANK_DEBUG_REQUESTS_TOTAL should increment
    rank_debug_metric = _get_metric_value('neuron_rag_rank_debug_requests_total')
    assert rank_debug_metric >= 1


def test_memory_linking_and_links_endpoint():
    # Create a case first via anomaly ingestion path to ensure case exists (reuse existing simple path)
    # If there is an existing case creation endpoint we use it; otherwise we simulate by creating a case directly.
    # Use core case creation endpoint if present
    case_resp = client.post('/cases', json={"title": "Memory Link Test"})
    if case_resp.status_code != 200:
        # Fallback: create an anomaly to spawn a case if implementation differs
        anomaly = {"id": "anom_mem_test", "tenant": "tenantA", "detector": "baseline", "score": 0.9}
        client.post('/anomalies', json=anomaly)
        # attempt basic listing heuristic to fetch case id
        cases_list = client.get('/cases').json()
        case_id = cases_list['items'][0]['id']
    else:
        case_id = case_resp.json()['case']['id']
    artifact_id = 'artifact_debug_1'
    # Ingest artifact
    resp = client.post('/memory/artifact', json={"artifact_id": artifact_id, "case_id": case_id})
    assert resp.status_code == 200
    # List links
    links = client.get(f'/memory/{artifact_id}/links').json()
    assert links['artifact_id'] == artifact_id
    assert links['count'] >= 1
    # Metric presence
    val = _get_metric_value('neuron_memory_artifact_link_total', {"link_type": "artifact_case"})
    assert val >= 1


def test_probe_loop_single_cycle_helper():
    before = _get_metric_value('neuron_retrieval_probe_total')
    _run_retrieval_probe_once()
    after = _get_metric_value('neuron_retrieval_probe_total')
    assert after >= before + 1

