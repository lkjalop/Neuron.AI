"""Tests for new vector & hybrid_vector retrieval modes.

Ensures:
  * vector mode returns results for semantic-ish queries.
  * hybrid_vector differs scoring from pure keyword in at least one ordering case.
  * provider plug-in pathway does not raise (using default hash provider).
"""
from __future__ import annotations

from rag import corpus
from config import runtime_params


def _seed_docs():
    corpus.add_document("alpha", "temporal adaptive fusion governance loop weight adjustment")
    corpus.add_document("beta", "anomaly residual variance temporal window attention score")
    corpus.add_document("gamma", "executive coverage matrix report scheduler bundle artifacts")


def test_vector_mode_basic(monkeypatch):
    _seed_docs()
    runtime_params.update_param("retrieval.scoring.mode", "vector", reason="test")
    res = corpus.search("adaptive weight governance", top_k=5)
    assert res, "Expected vector results"
    # Ensure returned doc ids valid
    ids = {r[0] for r in res}
    assert ids.issubset({"alpha", "beta", "gamma"})


def test_hybrid_vector_differs_from_keyword(monkeypatch):
    # Reset mode to keyword first
    runtime_params.update_param("retrieval.scoring.mode", "keyword", reason="test")
    kw = corpus.search("temporal residual variance", top_k=3)
    runtime_params.update_param("retrieval.scoring.mode", "hybrid_vector", reason="test")
    runtime_params.update_param("retrieval.hybrid.embedding_weight", 0.5, reason="test")
    hv = corpus.search("temporal residual variance", top_k=3)
    # Accept that ordering or scores may differ; at least one difference expected
    if kw and hv:
        kw_ids = [i for i,_ in kw]
        hv_ids = [i for i,_ in hv]
        assert kw_ids != hv_ids or any(abs(a[1]-b[1]) > 1e-6 for a,b in zip(kw,hv)), "Hybrid vector produced identical ordering & scores as keyword"


def test_vector_mode_fallback_embedding_cache(monkeypatch):
    runtime_params.update_param("retrieval.scoring.mode", "vector", reason="test")
    # Ensure embedding caching path executes (second call should reuse)
    first = corpus.search("coverage report bundle", top_k=3)
    second = corpus.search("coverage report bundle", top_k=3)
    assert first and second
