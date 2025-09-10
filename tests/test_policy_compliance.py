import json, time
from pathlib import Path
from policy import dsl
from policy import compliance


def test_policy_load_and_score(tmp_path, monkeypatch):
    policy_path = tmp_path / 'policy.json'
    policy = {
        "version": 1,
        "id": "p1",
        "allowed_adjust_range": {"detection.temporal.weight": [0.05, 0.3]},
        "min_coverage_by_class": {"MITRE.TA0001": 0.5},
        "required_techniques": ["T1003", "T1047"],
        "exceptions": [
            {"id": "ex1", "technique": "T1047", "reason": "legacy", "expires": time.time() + 3600}
        ]
    }
    policy_path.write_text(json.dumps(policy), encoding='utf-8')
    loaded = dsl.load_policy(policy_path)
    assert loaded['id'] == 'p1'
    # Mock coverage summary
    monkeypatch.setattr(compliance, 'coverage_summary', lambda: {
        "by_class": {"MITRE.TA0001": 0.5},
        "techniques": ["T1003"],
    })
    # Mock runtime param
    class _RP:
        def get_param(self, k):
            if k == 'detection.temporal.weight':
                return 0.1
            return None
    monkeypatch.setattr(compliance, 'runtime_params', _RP())
    score_obj = compliance.compute_score(loaded)
    assert 0 <= score_obj['score'] <= 1
    comps = score_obj['components']
    assert comps['coverage'] == 1.0  # met required exactly
    assert comps['requirements'] > 0.0  # one technique exempted, one present


def test_exception_expiry():
    policy = {
        "version": 1,
        "id": "p2",
        "exceptions": [
            {"id": "ex_now", "technique": "T1", "expires": time.time() - 10},
            {"id": "ex_future", "technique": "T2", "expires": time.time() + 1000},
        ]
    }
    active = dsl.active_exceptions(policy)
    ids = {e['id'] for e in active}
    assert 'ex_future' in ids and 'ex_now' not in ids
