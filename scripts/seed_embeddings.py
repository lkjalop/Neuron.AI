"""Seed embeddings for vulnerabilities & knowledge articles.

Usage:
  $env:NEON_DATABASE_URL="postgres://..."; python -m scripts.seed_embeddings --model-version hash64
"""
from __future__ import annotations

import argparse, asyncio, json, time
from typing import List, Tuple
from services.embedding_service import text_to_vector
from storage.embedding_store import upsert_embedding
from storage import postgres


async def fetch_targets(limit: int) -> List[Tuple[str, str]]:
    rows = await postgres.fetch(
        """
        SELECT id, properties FROM graph_nodes
        WHERE node_type IN ('KNOWLEDGE_ARTICLE','VULNERABILITY')
        LIMIT $1
        """,
        limit,
    )
    out: List[Tuple[str, str]] = []
    for r in rows:
        nid = r[0]
        props = r[1]
        title = None
        if isinstance(props, dict):
            title = props.get('title') or props.get('cve_id') or props.get('technique')
        if not title:
            title = nid
        out.append((nid, title))
    return out


async def seed(model_version: str, limit: int, dims: int):
    targets = await fetch_targets(limit)
    for nid, text in targets:
        vec = text_to_vector(text, dims=dims)
        await upsert_embedding(nid, vec, model_version)
    print(f"Seeded {len(targets)} embeddings (model={model_version}).")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model-version', default='hash64')
    ap.add_argument('--limit', type=int, default=500)
    ap.add_argument('--dims', type=int, default=64)
    args = ap.parse_args()
    t0 = time.time()
    await seed(args.model_version, args.limit, args.dims)
    print(f"Elapsed: {time.time()-t0:.2f}s")

if __name__ == '__main__':  # pragma: no cover
    asyncio.run(main())
