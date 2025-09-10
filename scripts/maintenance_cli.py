"""Lightweight maintenance CLI for persistence utilities.

Usage (PowerShell examples):
  python -m scripts.maintenance_cli save-all
  python -m scripts.maintenance_cli load-all
  python -m scripts.maintenance_cli export-corpus artifacts/corpus_export.json
  python -m scripts.maintenance_cli import-corpus artifacts/corpus_export.json
"""
from __future__ import annotations

import sys, json
from pathlib import Path

try:
    from rag import corpus as rag_corpus  # type: ignore
except Exception:
    rag_corpus = None  # type: ignore

try:
    from threat import model_registry  # type: ignore
except Exception:
    model_registry = None  # type: ignore


def cmd_save_all():
    saved = {}
    if rag_corpus:
        saved["corpus_docs"] = rag_corpus.save()
    if model_registry:
        saved["threat_models"] = model_registry.save()
    print(json.dumps({"saved": saved}, indent=2))


def cmd_load_all():
    loaded = {}
    if rag_corpus:
        loaded["corpus_docs"] = rag_corpus.load()
    if model_registry:
        loaded["threat_models"] = model_registry.load()
    print(json.dumps({"loaded": loaded}, indent=2))


def cmd_export_corpus(path: str):
    if not rag_corpus:
        print("corpus module unavailable", file=sys.stderr)
        return 2
    data = [rag_corpus.get_document(d["id"]) for d in rag_corpus.list_documents()]  # type: ignore
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"exported {len(data)} docs to {path}")
    return 0


def cmd_import_corpus(path: str):
    if not rag_corpus:
        print("corpus module unavailable", file=sys.stderr)
        return 2
    p = Path(path)
    if not p.exists():
        print(f"file not found: {path}", file=sys.stderr)
        return 3
    data = json.loads(p.read_text(encoding="utf-8"))
    count = 0
    if isinstance(data, list):
        for rec in data:
            if isinstance(rec, dict) and rec.get("id") and rec.get("text"):
                rag_corpus.add_document(rec["id"], rec["text"], rec.get("metadata"))  # type: ignore
                count += 1
    print(f"imported {count} docs from {path}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "save-all":
        cmd_save_all()
        return 0
    if cmd == "load-all":
        cmd_load_all()
        return 0
    if cmd == "export-corpus":
        if len(argv) < 3:
            print("missing path argument", file=sys.stderr)
            return 1
        return cmd_export_corpus(argv[2])
    if cmd == "import-corpus":
        if len(argv) < 3:
            print("missing path argument", file=sys.stderr)
            return 1
        return cmd_import_corpus(argv[2])
    print(f"unknown command: {cmd}")
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv))
