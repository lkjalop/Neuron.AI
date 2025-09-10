"""Qdrant client stub.

Uses official qdrant-client if installed; otherwise exposes no-op placeholders.
"""
from __future__ import annotations

import os
from typing import Any, List, Sequence

try:  # pragma: no cover - optional dependency
    from qdrant_client import QdrantClient  # type: ignore
except Exception:  # pragma: no cover
    QdrantClient = None  # type: ignore

_CLIENT = None


def client():  # noqa: D401
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    url = os.getenv("QDRANT_URL")
    key = os.getenv("QDRANT_API_KEY")
    if QdrantClient and url and key:
        try:
            _CLIENT = QdrantClient(url=url, api_key=key, timeout=3.0)
        except Exception:
            _CLIENT = None
    return _CLIENT


def upsert_vectors(collection: str, ids: Sequence[str], vectors: Sequence[Sequence[float]], payloads: Sequence[dict[str, Any]] | None = None):
    c = client()
    if not c:
        return False
    try:
        c.upsert(collection_name=collection, points=[{"id": ids[i], "vector": vectors[i], "payload": (payloads[i] if payloads else {})} for i in range(len(ids))])
        return True
    except Exception:
        return False


__all__ = ["client", "upsert_vectors"]
