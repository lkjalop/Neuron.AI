import pytest

try:
    from core.retrieval.planner import orchestrate
except Exception:  # pragma: no cover
    orchestrate = None  # type: ignore


def test_orchestrate_runs(monkeypatch):
    if orchestrate is None:
        pytest.skip('orchestrate not available')
    # Monkeypatch retrieval to deterministic output
    def fake_retrieve(q, k=5):
        return [{"doc": "DOC1", "chunk_id": 0, "score": 1.0, "explanation": {"matched_tokens": ["CVE-2024-1234", "30"]}}]
    def fake_corrective(query, draft_answer, k=5, threshold=2):
        return {"refined": False, "unsupported_count": 0, "added_terms": [], "context": []}
    import core.retrieval.interface as I  # type: ignore
    monkeypatch.setattr(I, 'retrieve_context', fake_retrieve)
    monkeypatch.setattr(I, 'corrective_refine', fake_corrective)
    out = orchestrate('Assess exploit patch risk', k=2)
    assert 'plan' in out and 'contexts' in out and 'corrective' in out
