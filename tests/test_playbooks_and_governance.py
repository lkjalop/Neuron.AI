import sys, time
import pathlib
sys.path.insert(0, str(pathlib.Path('src').resolve()))
from fastapi.testclient import TestClient
from core.main import app  # type: ignore

client = TestClient(app)
API_KEY_HEADER = {"x-api-key": "adminkey"}

def create_case():
    anomaly_id = 'pb-anom-' + str(time.time())
    r = client.post(f"/cases/from_anomaly/{anomaly_id}", headers=API_KEY_HEADER)
    assert r.status_code == 200
    return r.json()["case"]["id"]

def test_playbook_execute_and_rule_eval():
    cid = create_case()
    # Reopen to satisfy rule condition (status reopened)
    client.post(f"/cases/{cid}/close", json={"reason": "test"}, headers=API_KEY_HEADER)
    client.post(f"/cases/{cid}/reopen", json={}, headers=API_KEY_HEADER)

    # Evaluate rules (should match promote_on_reopened)
    r = client.post(f"/response/rules/evaluate/{cid}", headers=API_KEY_HEADER)
    assert r.status_code == 200
    js = r.json()
    assert 'promote_on_reopened' in js['matched']
    # Playbook listing
    r = client.get('/response/playbooks', headers=API_KEY_HEADER)
    assert r.status_code == 200
    assert any(pb['id']=='basic_containment' for pb in r.json().get('playbooks',[]))
    # Direct playbook execution
    r = client.post('/response/playbooks/execute/basic_containment', json={"case_id": cid}, headers=API_KEY_HEADER)
    assert r.status_code == 200
    res = r.json()
    assert res.get('playbook') == 'basic_containment'

    # Evidence attachment
    r = client.post(f"/cases/{cid}/evidence", json={"type": "log", "summary": "attached log"}, headers=API_KEY_HEADER)
    assert r.status_code == 200
    assert r.json().get('case_id') == cid

    # Governance bypass
    r = client.post('/governance/policy/bypass', json={"reason": "manual_override"}, headers=API_KEY_HEADER)
    assert r.status_code == 200
    r = client.get('/governance/policy/bypass', headers=API_KEY_HEADER)
    assert r.status_code == 200
    items = r.json().get('items', [])
    assert any(it['reason']=='manual_override' for it in items)

    # Metrics presence sanity
    metrics_text = client.get('/metrics', headers=API_KEY_HEADER).text
    for fam in [
        'neuron_response_playbook_step_total',
        'neuron_response_step_latency_seconds',
        'neuron_response_rule_eval_total',
        'neuron_governance_policy_bypass_total'
    ]:
        assert fam in metrics_text
