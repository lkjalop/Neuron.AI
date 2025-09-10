from embeddings.base import provider, DummyEmbedding, OpenAIEmbedding
import os

def test_embedding_fallback_without_key(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setenv('EMBEDDING_PROVIDER', 'openai')
    p = provider()
    # Should fallback to DummyEmbedding due to missing key
    assert isinstance(p, DummyEmbedding)
    vecs = p.embed(['hello', 'world'])
    assert len(vecs) == 2 and all(isinstance(v, list) for v in vecs)


def test_embedding_openai_instantiation(monkeypatch):
    # If key present but requests missing, still fallback gracefully
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test')
    monkeypatch.setenv('EMBEDDING_PROVIDER', 'openai')
    # Temporarily simulate missing requests by removing from sys.modules if present
    import sys
    saved = sys.modules.get('requests')
    if 'requests' in sys.modules:
        del sys.modules['requests']
    try:
        p = provider()
        # Could be OpenAIEmbedding if requests available (unlikely here) or DummyEmbedding fallback
        assert isinstance(p, (OpenAIEmbedding, DummyEmbedding))
    finally:
        if saved is not None:
            sys.modules['requests'] = saved
