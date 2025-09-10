"""Script: ingest markdown docs into knowledge graph as KnowledgeArticle nodes.

Usage (PowerShell):
  $env:NEON_DATABASE_URL="postgres://..."; python -m scripts.ingest_docs_to_knowledge_graph --docs-dir docs

Behavior:
  - Scans *.md under docs-dir (non-recursive by default unless --recursive set)
  - Extracts first '# ' heading as title; slug = normalized filename or heading
  - Inserts/updates graph_nodes rows with node_type=KNOWLEDGE_ARTICLE

Limitations:
  - No vector embedding (Batch 3 will enrich with embeddings)
  - Basic markdown stripping (headings + code fences preserved as-is)
"""
from __future__ import annotations

import argparse, os, re, asyncio, pathlib
from typing import List
from storage.graph_store import upsert_knowledge_article


HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def extract_title(body: str) -> str:
    m = HEADING_RE.search(body)
    if m:
        return m.group(1).strip()
    # fallback first line
    first_line = body.strip().splitlines()[0:1]
    return first_line[0][:120] if first_line else "Untitled"


def slugify(text: str) -> str:
    import re as _re
    t = text.lower()
    t = _re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t or "article"


async def ingest(files: List[pathlib.Path]):
    for p in files:
        body = p.read_text(encoding="utf-8", errors="ignore")
        title = extract_title(body)
        slug = slugify(title or p.stem)
        await upsert_knowledge_article(slug, title, body)


def collect_files(root: str, recursive: bool) -> List[pathlib.Path]:
    base = pathlib.Path(root)
    pattern = "**/*.md" if recursive else "*.md"
    return [p for p in base.glob(pattern) if p.is_file()]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs-dir", default="docs")
    ap.add_argument("--recursive", action="store_true")
    args = ap.parse_args()
    files = collect_files(args.docs_dir, args.recursive)
    if not files:
        print("No markdown files found.")
        return
    print(f"Ingesting {len(files)} markdown files into knowledge graph...")
    await ingest(files)
    print("Done.")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
