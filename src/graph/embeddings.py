"""Lightweight Embedding Prototype (Node2Vec-style random walks + Skip-Gram).

This is a minimal, dependency-light embedding generator for experimentation.
It does NOT implement negative sampling with optimized vector math; instead
it uses a simple in-memory training loop. Suitable for small graphs only.

Future upgrade path: migrate to gensim or PyTorch Geometric for scalability.
"""
from __future__ import annotations

from typing import Dict, List, Tuple
import math
import random

from .relationships import get_graph

_EMBEDDINGS: Dict[str, List[float]] = {}
_EMBED_META: Dict[str, float | int] = {}


def _random_walk(start: str, neighbor_map: Dict[str, List[str]], walk_length: int) -> List[str]:
    path = [start]
    cur = start
    for _ in range(walk_length - 1):
        nbrs = neighbor_map.get(cur) or []
        if not nbrs:
            break
        cur = random.choice(nbrs)
        path.append(cur)
    return path


def train_embeddings(dim: int = 32, walks_per_node: int = 4, walk_length: int = 8, epochs: int = 2, lr: float = 0.05, window: int = 2, seed: int | None = None):
    if seed is not None:
        random.seed(seed)
    g = get_graph()
    nodes = g.nodes()
    if not nodes:
        # Record meta with dimension for test expectations even when graph empty
        global _EMBED_META, _EMBEDDINGS
        _EMBEDDINGS = {}
        _EMBED_META = {
            "dim": dim,
            "walks_per_node": walks_per_node,
            "walk_length": walk_length,
            "epochs": epochs,
        }
        return _EMBEDDINGS
    neighbor_map: Dict[str, List[str]] = {n: g.neighbors(n) for n in nodes}
    # Initialize embeddings
    global _EMBEDDINGS, _EMBED_META
    _EMBEDDINGS = {n: [random.uniform(-0.5, 0.5) for _ in range(dim)] for n in nodes}
    def _norm(v: List[float]):
        mag = math.sqrt(sum(x*x for x in v)) or 1.0
        for i, val in enumerate(v):
            v[i] = val / mag
    # Generate walks
    walks: List[List[str]] = []
    for n in nodes:
        for _ in range(walks_per_node):
            walks.append(_random_walk(n, neighbor_map, walk_length))
    # Training (Skip-Gram style cosine push/pull small variant)
    for _epoch in range(epochs):
        random.shuffle(walks)
        for w in walks:
            for i, center in enumerate(w):
                center_vec = _EMBEDDINGS[center]
                # context window
                left = max(0, i - window)
                right = min(len(w), i + window + 1)
                for j in range(left, right):
                    if j == i:
                        continue
                    ctx = w[j]
                    ctx_vec = _EMBEDDINGS[ctx]
                    # positive update
                    dot = sum(a*b for a, b in zip(center_vec, ctx_vec))
                    grad = lr * (1 - dot)
                    for k in range(dim):
                        a = center_vec[k]
                        b = ctx_vec[k]
                        center_vec[k] += grad * b
                        ctx_vec[k] += grad * a
                    _norm(center_vec)
                    _norm(ctx_vec)
    _EMBED_META = {
        "dim": dim,
        "walks_per_node": walks_per_node,
        "walk_length": walk_length,
        "epochs": epochs,
    }
    return _EMBEDDINGS


def get_embedding(node_id: str) -> List[float] | None:
    return _EMBEDDINGS.get(node_id)


def get_embedding_meta():
    return _EMBED_META


__all__ = ["train_embeddings", "get_embedding", "get_embedding_meta"]
