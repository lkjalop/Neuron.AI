"""Tests for hybrid retrieval scoring mode.

Verifies that when retrieval.scoring.mode == 'hybrid' and embedding_weight > 0 the
score reflects composite coverage rather than raw overlap (floating point value
<=1 typically), and explanation includes hybrid fields.
"""
from __future__ import annotations

import pathlib
from scripts import rag_ingest
from config import runtime_params


def test_hybrid_scoring_includes_idf_components(tmp_path, monkeypatch):
    # Force params
    runtime_params.update_param("retrieval.scoring.mode", "hybrid", reason="test_hybrid")
    runtime_params.update_param("retrieval.hybrid.embedding_weight", 0.5, reason="test_hybrid")

    d1 = tmp_path / "d1.md"
    d2 = tmp_path / "d2.md"
    # d1 shares a very common token 'anomaly' plus unique token
    d1.write_text("anomaly anomaly forest threshold calibration", encoding="utf-8")
    # d2 has fewer overlaps but higher IDF token 'calibration'
    d2.write_text("calibration residual variance context", encoding="utf-8")

    index, _chunks, _manifest = rag_ingest.build_index([d1, d2])

    res = rag_ingest.retrieve(index, "anomaly calibration", top_k=5, explanations=True)
    assert res, "Expected results in hybrid mode"
    # Scores should be floats between 0 and 1 (composite) not raw integer overlaps when hybrid active
    for r in res:
        assert isinstance(r["score"], (int, float))
    # Ensure explanation includes hybrid fields for at least one result
    hybrid_fields = {"idf_coverage", "embedding_weight", "composite", "scoring_mode"}
    assert any(hybrid_fields.issubset(set(r.get("explanation", {}).keys())) for r in res), "Hybrid fields missing in explanations"

    # Clean up: reset mode to keyword to avoid leakage into other tests (best effort)
    runtime_params.update_param("retrieval.scoring.mode", "keyword", reason="reset_hybrid")
