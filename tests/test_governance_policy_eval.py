import json, time, pathlib
from fastapi.testclient import TestClient
from core.main import app
from config import runtime_params
from core import metrics


def _headers():
    return {"x-api-key": "adminkey"}


def test_policy_eval_trigger_and_metrics(monkeypatch, tmp_path):
    # Write a simple policy file
    p = tmp_path / 'config'
    p.mkdir()
    policy_path = p / 'policy.json'
    policy = {
        "id": "policy-test",
        "min_coverage_by_class": {"execution": 0.5},
        "required_techniques": ["T1003"],
        "allowed_adjust_range": {"fusion.temporal.weight": [0.0, 2.0]},
    }
    policy_path.write_text(json.dumps(policy), encoding='utf-8')
    # Monkeypatch policy file path in evaluator
    import governance.policy_eval as pe  # type: ignore
    monkeypatch.setattr(pe, '_POLICY_FILE', policy_path)
    # Ensure params enabled
    runtime_params.update_param('governance.policy.eval.enabled', True, reason='test', actor='test')
    runtime_params.update_param('governance.policy.eval.sign', False, reason='test', actor='test')
    client = TestClient(app)
    r = client.post('/governance/policy/eval/trigger', headers=_headers())
    assert r.status_code == 200, r.text
    data = r.json()
    assert 'score' in data and data['status'] == 'ok'
    # Metrics snapshot
    mtext = client.get('/metrics').text
    assert 'neuron_governance_policy_eval_total' in mtext
    assert 'neuron_governance_policy_score' in mtext
    assert 'neuron_governance_policy_component' in mtext
    # Status endpoint
    r2 = client.get('/governance/policy/eval', headers=_headers())
    assert r2.status_code == 200
    js2 = r2.json()
    assert js2.get('status') == 'ok'
