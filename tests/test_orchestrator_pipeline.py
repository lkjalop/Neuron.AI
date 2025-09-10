import pytest

try:
    from core.retrieval.orchestrator import run_pipeline
except Exception:
    run_pipeline = None  # type: ignore


def test_run_pipeline_basic(monkeypatch):
    if run_pipeline is None:
        pytest.skip("orchestrator missing")
    # Monkeypatch underlying components for determinism
    from core import retrieval as _unused  # noqa: F401
    import core.retrieval.planner as P  # type: ignore
    import core.retrieval.interface as I  # type: ignore

    def fake_plan(q: str):
        return {"query": q, "subqueries": [{"stage": "inventory", "q": q+" assets"}]}  # minimal valid
    monkeypatch.setattr(P, 'plan', fake_plan)

    def fake_retrieve(q: str, k: int = 5):
        return [{"doc": "a.md", "chunk_id": 0, "score": 1.0, "explanation": {"matched_tokens": ["CVE-2024-1234", "30"]}}]
    monkeypatch.setattr(I, 'retrieve_context', fake_retrieve)

    def fake_run_corrective(q: str, initial_answer: str | None = None, k: int = 5):
        return {"iterations": 1, "history": [{"unsupported_count":0,"refined":False}], "final_context": [], "final_answer": initial_answer or q}
    monkeypatch.setattr(I, 'run_corrective', fake_run_corrective)

    out = run_pipeline("Assess risk")
    assert 'trace_id' in out and out['plan'] and out['contexts'] and out['corrective']
    assert out['corrective']['iterations'] == 1
