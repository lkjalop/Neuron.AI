import hashlib
from pathlib import Path
import importlib
import os


def test_manifest_hash_match(monkeypatch):
    doc = Path("docs/NEURON_PHASES.md")
    hash_file = Path("audit/CANONICAL_DOC_HASH")
    h = hashlib.sha256(doc.read_bytes()).hexdigest()
    hash_file.write_text(h)
    monkeypatch.delenv("ALLOW_CANONICAL_DOC_DRIFT", raising=False)
    import core.main  # noqa: F401
    # No exception means success
    assert True


def test_manifest_hash_mismatch(monkeypatch):
    doc = Path("docs/NEURON_PHASES.md")
    hash_file = Path("audit/CANONICAL_DOC_HASH")
    original = hashlib.sha256(doc.read_bytes()).hexdigest()
    hash_file.write_text("deadbeef")
    monkeypatch.delenv("ALLOW_CANONICAL_DOC_DRIFT", raising=False)
    try:
        import sys
        if 'core.main' in sys.modules:
            del sys.modules['core.main']
        import core.main  # noqa: F401
        assert False, "Expected RuntimeError due to hash mismatch"
    except RuntimeError:
        pass
    finally:
        hash_file.write_text(original)
