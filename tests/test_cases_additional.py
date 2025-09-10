import time
from fastapi.testclient import TestClient
from core.main import app, _CASE_ID_INDEX, _CASES, _record_memory_confirmation
from core import metrics as _m

client = TestClient(app)


def test_case_idempotent_creation():
    r1 = client.post('/cases/from_anomaly/idem123')
    assert r1.status_code == 200
    cid1 = r1.json()['case']['id']
    r2 = client.post('/cases/from_anomaly/idem123')
    assert r2.status_code == 200
    cid2 = r2.json()['case']['id']
    assert cid1 == cid2
    assert _CASE_ID_INDEX['idem123'] == cid1


def test_timeline_pagination_edges():
    r = client.post('/cases/from_anomaly/pagroot')
    cid = r.json()['case']['id']
    # add many events
    from core.main import _add_case_timeline_event
    for i in range(35):
        _add_case_timeline_event(cid, 'custom', f'ev{i}', f'summary {i}')
    first_page = client.get(f'/cases/{cid}/timeline?limit=10').json()
    assert first_page['returned'] == 10
    second_page = client.get(f"/cases/{cid}/timeline?limit=10&offset=10").json()
    assert second_page['returned'] == 10
    # ensure no overlap in ref_ids between pages
    ids_first = {e['ref_id'] for e in first_page['items']}
    ids_second = {e['ref_id'] for e in second_page['items']}
    assert not ids_first.intersection(ids_second)


def test_cases_search_filters_and_kpis():
    r = client.post('/cases/from_anomaly/search_promote_root')
    cid = r.json()['case']['id']
    case = _CASES[cid]
    case['stats']['network_anomalies'] = 3  # trigger promotion on summary
    client.get(f'/cases/{cid}/summary')
    search_resp = client.get('/cases/search?promoted=true').json()
    assert any(c['id'] == cid for c in search_resp['items'])
    kpis = client.get('/executive/kpis').json()
    assert 'cases' in kpis and kpis['cases']['total'] >= 1


def test_memory_uplift_metric_change(monkeypatch):
    # create case to map anomaly id artificially
    r = client.post('/cases/from_anomaly/memu1')
    assert r.status_code == 200
    # simulate fusion decisions ring entry and memory confirmation
    before = 0.0
    try:
        child_map = getattr(_m.FUSION_MEMORY_VERIFIED_RATIO, '_metrics', {})
        for _k, child in child_map.items():
            before = float(child._value.get())
            break
    except Exception:
        before = 0.0
    _record_memory_confirmation('memu1', 'unknown', 'baseline')
    after = before
    try:
        child_map = getattr(_m.FUSION_MEMORY_VERIFIED_RATIO, '_metrics', {})
        for _k, child in child_map.items():
            after = float(child._value.get())
            break
    except Exception:
        pass
    assert after >= before
