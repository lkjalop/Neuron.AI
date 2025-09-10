import json, types
import pytest

# Attempt imports (graceful if missing heavy deps)
try:
    from core.retrieval import interface as R
except Exception:  # pragma: no cover
    R = types.SimpleNamespace(retrieve_context=lambda q, k=5: [], corrective_refine=lambda q,a,k=5,threshold=2: {})  # type: ignore

try:
    from core.retrieval.planner import plan
except Exception:  # pragma: no cover
    plan = None  # type: ignore


def test_rerank_disabled_graceful(monkeypatch):
    # Force rerank disabled
    class DummyRP:
        def get_param(self, name):
            if name == 'retrieval.rerank.enabled':
                return 0
            return None
    monkeypatch.setattr(R, 'runtime_params', DummyRP())
    res = R.retrieve_context('exploit evidence', k=2)
    # should not raise and return list
    assert isinstance(res, list)


def test_corrective_refine_paths(monkeypatch):
    # Provide deterministic context
    def fake_retrieve(q, k=5):
        return [{"explanation": {"matched_tokens": ["cve-2024-1234", "30"]}, "doc": "DOC", "chunk_id": 0, "score": 1.0}]
    monkeypatch.setattr(R, 'retrieve_context', fake_retrieve)
    # Case 1: unsupported tokens below threshold triggers skip
    out1 = R.corrective_refine('query', 'Answer referencing CVE-2024-1234 and 30', k=3, threshold=5)
    assert out1['refined'] is False
    # Case 2: above threshold triggers refine (inject fake unsupported tokens)
    def critic_override(answer, ctx):
        return {"unsupported": ["CVE-2025-9999", "CVE-2025-9998", "55"], "unsupported_count": 3}
    monkeypatch.setattr(R, '_critic_detect_unsupported', critic_override)
    out2 = R.corrective_refine('query', 'A', k=3, threshold=2)
    assert out2['refined'] is True
    assert any('CVE-2025-9999' in t for t in out2.get('added_terms', []))


def test_planner_schema(monkeypatch):
    if plan is None:
        pytest.skip('planner not available')
    # Valid
    p = plan('Assess exploit risk for critical assets patch status')
    assert 'subqueries' in p and p.get('query')
    # Inject invalid (simulate internal failure) by monkeypatching decompose
    from core.retrieval import planner as P
    def bad_decompose(q):
        return {"query": q, "subqueries": []}  # invalid (empty)
    monkeypatch.setattr(P, 'decompose', bad_decompose)
    p2 = P.plan('test bad')
    assert 'error' in p2
