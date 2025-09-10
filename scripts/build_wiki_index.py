"""Build Wiki Index

Scans docs/ directory and produces a lightweight JSON index (file -> title, first heading)
for downstream retrieval / RAG augmentation.
"""
from __future__ import annotations

import pathlib, json, re

DOCS_DIR = pathlib.Path("docs")
OUTPUT = pathlib.Path("artifacts/wiki_index.json")


def extract_title(text: str) -> str:
    for line in text.splitlines():
        if line.strip().startswith("#"):
            return line.lstrip("# ").strip()
    return "Untitled"


def build_index():
    index = {}
    for p in DOCS_DIR.glob("*.md"):
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            title = extract_title(content)
            index[str(p)] = {"title": title, "chars": len(content)}
        except Exception:
            continue
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return index


def main():
    idx = build_index()
    print(json.dumps({"files": len(idx)}, indent=2))


if __name__ == "__main__":
    main()
