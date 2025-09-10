from scripts.rag_ingest import build_index, retrieve
import pathlib

def test_rag_retrieval_soc_iforest_phrase():
    doc = pathlib.Path('docs/SOC_IFOREST_OPERATIONS.md')
    assert doc.exists(), 'SOC_IFOREST_OPERATIONS.md missing'
    idx, _chunks, _manifest = build_index([doc])
    # Query containing phrase tokens present in doc (heuristic + extreme)
    results = retrieve(idx, 'extreme heuristic value threshold')
    assert results, 'Expected at least one retrieval result'
    # Ensure returned chunk includes token 'extreme'
    assert any('extreme' in r['text'].lower() for r in results)
