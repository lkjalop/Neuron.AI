import time

from config import runtime_params
from config.runtime_params import update_param


def _make_case(**overrides):
    base = {
        "id": "case-xyz",
        "created_ts": time.time() - 4000,  # overdue relative to 1h SLA
        "last_confidence": 0.82,
        "promoted": True,
        "memory_artifact_ids": [],
    }
    base.update(overrides)
    return base


def test_recommendation_ordering_and_playbook_ids():
    from core.response.engine import build_recommendations, playbook_preview

    case = _make_case()
    recs = build_recommendations(case)
    assert recs, "recommendations should not be empty when enabled"
    # Ensure deterministic ordering by score then action name
    scores = [r["score"] for r in recs]
    assert scores == sorted(scores, reverse=True), "scores should be descending"
    # Playbook IDs stable
    preview1 = playbook_preview(case)
    preview2 = playbook_preview(case)
    assert preview1["actions"] and preview2["actions"]
    ids1 = [a["id"] for a in preview1["actions"]]
    ids2 = [a["id"] for a in preview2["actions"]]
    assert ids1 == ids2, "playbook IDs must be deterministic"


def test_governance_composite_gating_blocks_out_of_bounds():
    from core.response.engine import eligible_for_auto_escalation

    # Enable auto escalation
    update_param("response.auto.escalate.enabled", True, reason="test")
    case = _make_case()
    # Composite too low
    assert not eligible_for_auto_escalation(case, composite=0.1)
    # Composite too high
    assert not eligible_for_auto_escalation(case, composite=0.95)
    # In bounds should pass (age, promoted, confidence all satisfied by base case)
    assert eligible_for_auto_escalation(case, composite=0.5)


def test_auto_escalation_decision_rate_limit(monkeypatch):
    from core.main import _RESPONSE_AUTOMATION_HISTORY, _automation_evaluate_once

    # Tighten hour limit
    update_param("response.auto.escalate.enabled", True, reason="test")
    update_param("response.auto.escalate.max_per_hour", 1, reason="test")
    # Seed a case in global store
    from core.main import _CASES
    case = _make_case(id="case-rate-limit")
    _CASES[case["id"]] = case

    # First evaluation should record one decision
    _RESPONSE_AUTOMATION_HISTORY.clear()
    _automation_evaluate_once()
    first_len = len(_RESPONSE_AUTOMATION_HISTORY)
    assert first_len <= 1
    # Second evaluation immediately should not exceed rate limit
    _automation_evaluate_once()
    assert len(_RESPONSE_AUTOMATION_HISTORY) == first_len, "rate limit should block second decision"


def test_auto_escalation_requires_promotion():
    from core.response.engine import eligible_for_auto_escalation
    update_param("response.auto.escalate.enabled", True, reason="test")
    update_param("response.auto.escalate.require_promoted", True, reason="test")
    case = _make_case(promoted=False)
    assert not eligible_for_auto_escalation(case, composite=0.5)
    case_prom = _make_case(promoted=True)
    assert eligible_for_auto_escalation(case_prom, composite=0.5)


def test_memory_acquisition_recommendation_skipped_when_enough_artifacts():
    from core.response.engine import build_recommendations
    update_param("response.memory.min_artifacts_for_skip", 1, reason="test")
    # case with 1 artifact should skip acquisition (threshold is < 1)
    case = _make_case(memory_artifact_ids=["m1"], last_confidence=0.9)
    recs = build_recommendations(case)
    actions = [r["action"] for r in recs]
    assert "request_memory_acquisition" not in actions
    # case with 0 artifacts should include it
    case2 = _make_case(memory_artifact_ids=[], last_confidence=0.9)
    recs2 = build_recommendations(case2)
    actions2 = [r["action"] for r in recs2]
    assert "request_memory_acquisition" in actions2
