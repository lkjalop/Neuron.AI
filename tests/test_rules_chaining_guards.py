import tempfile, json, os, time
from fastapi.testclient import TestClient
from src.core.main import app

client = TestClient(app)

RULES_PATH_ENV = 'RESPONSE_RULES_PATH'

SIMPLE_BASE = [
  {"id": "r1", "description": "base rule", "match": "True", "action": "noop", "next": "r2"},
  {"id": "r2", "description": "second", "match": "False", "action": "noop"}
]

LOOP_RULES = [
  {"id": "a", "match": "True", "action": "noop", "next": "b"},
  {"id": "b", "match": "True", "action": "noop", "next": "a"}
]

DEPTH_RULES = []
# Construct > max depth (assuming default max depth 25 in implementation; build 30 chain)
for i in range(30):
    DEPTH_RULES.append({"id": f"d{i}", "match": "True", "action": "noop", **({"next": f"d{i+1}"} if i < 29 else {})})


def _write_rules(tempdir, rules):
    path = os.path.join(tempdir, 'rules.test.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rules, f)
    return path


def _scrape(metric_name: str):
    r = client.get('/metrics')
    assert r.status_code == 200
    return sum(1 for line in r.text.splitlines() if line.startswith(metric_name))


def test_rule_chain_loop_and_depth_metrics():
    with tempfile.TemporaryDirectory() as td:
        # Loop case
        loop_path = _write_rules(td, LOOP_RULES)
        os.environ[RULES_PATH_ENV] = loop_path
        client.post('/response/rules/reload')  # trigger reload
        # Depth exceed case
        depth_path = _write_rules(td, DEPTH_RULES)
        os.environ[RULES_PATH_ENV] = depth_path
        client.post('/response/rules/reload')
        # Basic case
        base_path = _write_rules(td, SIMPLE_BASE)
        os.environ[RULES_PATH_ENV] = base_path
        client.post('/response/rules/reload')
        # Scrape metrics counting samples with outcomes
        metrics_text = client.get('/metrics').text.splitlines()
        chain_samples = [l for l in metrics_text if l.startswith('neuron_response_rule_chain_total')]
        # Expect at least one loop_detected and one depth_exceeded sample lines (monotonic counters) plus ok
        assert any('result="loop_detected"' in l for l in chain_samples)
        assert any('result="depth_exceeded"' in l for l in chain_samples)
        assert any('result="ok"' in l for l in chain_samples)
