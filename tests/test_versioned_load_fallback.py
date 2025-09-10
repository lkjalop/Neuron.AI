import json, os, shutil
from pathlib import Path

# Import modules under test
from threat import model_registry
from rag import corpus


def write_legacy_threat_models(tmp_path: Path, models):
    f = tmp_path / 'artifacts' / 'threat_models.json'
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(models, indent=2), encoding='utf-8')
    return f

def write_legacy_corpus(tmp_path: Path, docs):
    f = tmp_path / 'artifacts' / 'rag_corpus.json'
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(docs, indent=2), encoding='utf-8')
    return f


def test_threat_model_legacy_load(tmp_path, monkeypatch):
    # Prepare legacy list (v0) models
    models = [
        {"id": "m1", "name": "Model1", "version": 1, "description": "d", "techniques": ["T1000"], "assets": ["A1"], "created_ts": 1.0, "updated_ts": 1.0, "metadata": {}},
        {"id": "m2", "name": "Model2", "version": 2, "description": "d2", "techniques": [], "assets": [], "created_ts": 2.0, "updated_ts": 2.0, "metadata": {}},
    ]
    legacy_file = write_legacy_threat_models(tmp_path, models)
    # Monkeypatch module persist path
    monkeypatch.setattr(model_registry, '_PERSIST_FILE', legacy_file)
    count = model_registry.load()
    assert count == 2
    # Save should rewrite to versioned format
    model_registry.save()
    data = json.loads(legacy_file.read_text(encoding='utf-8'))
    assert isinstance(data, dict) and data.get('version') == model_registry._ARTIFACT_VERSION
    assert 'models' in data and len(data['models']) == 2


def test_rag_corpus_legacy_load(tmp_path, monkeypatch):
    docs = [
        {"id": "d1", "text": "Alpha beta", "metadata": {"k": 1}},
        {"id": "d2", "text": "Gamma delta", "metadata": {}},
    ]
    legacy_file = write_legacy_corpus(tmp_path, docs)
    monkeypatch.setattr(corpus, '_PERSIST_FILE', legacy_file)
    count = corpus.load()
    assert count == 2
    corpus.save()
    data = json.loads(legacy_file.read_text(encoding='utf-8'))
    assert isinstance(data, dict) and data.get('version') == corpus._ARTIFACT_VERSION
    assert 'documents' in data and len(data['documents']) == 2
