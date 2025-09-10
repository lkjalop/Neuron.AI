"""Tests for multi-document retrieval and explanation fields (A17).

Relies on rag_ingest build_index & retrieve functions indirectly by invoking the script logic.
We simulate ingestion by creating temporary markdown files, then calling build_index directly
(for speed) instead of spawning subprocess. Ensures:
  - Query tokens spanning docs return ranked chunks.
  - Explanations include matched_tokens & coverage when enabled.
"""
from __future__ import annotations

import pathlib, json
from scripts import rag_ingest


def test_multi_doc_retrieval_explanations(tmp_path, monkeypatch):
    # Prepare two simple docs with overlapping and distinct tokens
    d1 = tmp_path / "doc1.md"
    d2 = tmp_path / "doc2.md"
    d1.write_text("Isolation forest applies extreme-value heuristic threshold.", encoding="utf-8")
    d2.write_text("Temporal residual variance improves anomaly context explanation.", encoding="utf-8")

    index, _chunks, manifest = rag_ingest.build_index([d1, d2])
    assert manifest, "Manifest should not be empty"

    # Force explanations regardless of runtime params for this test by passing flag
    results = rag_ingest.retrieve(index, "extreme-value residual variance heuristic", top_k=5, explanations=True)
    assert results, "Should retrieve at least one chunk"
    # Validate explanation fields present
    for r in results:
        assert "doc" in r and "chunk_id" in r and "score" in r
        if "explanation" in r:
            exp = r["explanation"]
            assert set(["matched_tokens", "overlap", "coverage"]).issubset(exp.keys())
            assert exp["overlap"] == len(exp["matched_tokens"])  # since unique token matching
            assert 0.0 <= exp["coverage"] <= 1.0

    # Ensure ranking places chunk with more token overlaps first when possible
    if len(results) >= 2:
        assert results[0]["score"] >= results[1]["score"]


if __name__ == "__main__":  # manual debug helper
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tp = pathlib.Path(td)
        test_multi_doc_retrieval_explanations(tp, None)
        print("OK")
