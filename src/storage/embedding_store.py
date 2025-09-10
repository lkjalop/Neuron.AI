"""Embedding persistence and retrieval.

Supports two modes:
 1. pgvector (if extension available and 'vector' column type present)
 2. JSONB fallback storing list[float] and performing brute-force cosine similarity in Python

Table (proposed):
  CREATE TABLE graph_node_embeddings (
      node_id TEXT PRIMARY KEY REFERENCES graph_nodes(id) ON DELETE CASCADE,
      model_version TEXT NOT NULL,
      dims INT NOT NULL,
      embedding JSONB NOT NULL, -- Always JSON for portability (wrap pgvector later)
      created_ts DOUBLE PRECISION NOT NULL
  );
Index for semantic filtering can be added later.
"""
from __future__ import annotations

from typing import List, Dict, Any, Tuple
import time, math, json

from . import postgres


async def upsert_embedding(node_id: str, vector: List[float], model_version: str) -> None:
    await postgres.execute(
        """
        INSERT INTO graph_node_embeddings (node_id, model_version, dims, embedding, created_ts)
        VALUES ($1,$2,$3,$4,$5)
        ON CONFLICT (node_id) DO UPDATE SET
          model_version=EXCLUDED.model_version,
          dims=EXCLUDED.dims,
          embedding=EXCLUDED.embedding
        """,
        node_id,
        model_version,
        len(vector),
        json.dumps(vector),
        float(time.time()),
    )


async def get_embedding(node_id: str) -> List[float] | None:
    rows = await postgres.fetch("SELECT embedding FROM graph_node_embeddings WHERE node_id=$1", node_id)
    if not rows:
        return None
    emb = rows[0][0]
    if isinstance(emb, list):
        return emb
    if isinstance(emb, str):
        try:
            return json.loads(emb)
        except Exception:
            return None
    return None


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x*y for x,y in zip(a,b))
    na = math.sqrt(sum(x*x for x in a)) or 1e-9
    nb = math.sqrt(sum(y*y for y in b)) or 1e-9
    return dot / (na*nb)


async def semantic_search(query_vec: List[float], limit: int = 10, min_score: float = 0.0) -> List[Tuple[str, float]]:
    # Brute force search; efficient enough for small N. Optimize later.
    rows = await postgres.fetch("SELECT node_id, embedding FROM graph_node_embeddings")
    results: List[Tuple[str, float]] = []
    for r in rows:
        node_id = r[0]
        emb = r[1]
        if isinstance(emb, str):
            try:
                emb = json.loads(emb)
            except Exception:
                continue
        if not isinstance(emb, list):
            continue
        score = _cosine(query_vec, emb)  # type: ignore[arg-type]
        if score >= min_score:
            results.append((node_id, score))
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:limit]


__all__ = [
    "upsert_embedding",
    "get_embedding",
    "semantic_search",
]
