"""Memory router exposing patterns and artifact correlation endpoints."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from core.memory_store import add_pattern, list_patterns, stats as _stats, match as _match, correlate_artifacts

router = APIRouter(tags=["memory"]) 

@router.post('/memory/patterns')
def memory_patterns_add(body: dict):
    pat = (body or {}).get("pattern")
    if not pat or not isinstance(pat, str):
        raise HTTPException(400, "pattern_required")
    tags = (body or {}).get("tags") or []
    ttl_s = (body or {}).get("ttl_s")
    try:
        if ttl_s is not None:
            ttl_s = int(ttl_s)
    except Exception:
        ttl_s = None
    rec = add_pattern(pat, tags=tags if isinstance(tags, list) else [], ttl_s=ttl_s)
    return {"created": rec}

@router.get('/memory/patterns')
def memory_patterns_search(q: str | None = None, limit: int = 50):
    try:
        limit = max(1, min(200, int(limit)))
    except Exception:
        limit = 50
    items = list_patterns(q=q, limit=limit)
    return {"items": items, "count": len(items)}

@router.get('/memory/patterns/stats')
def memory_patterns_stats():
    return _stats()

@router.post('/memory/patterns/match')
def memory_patterns_match(body: dict):
    blob = (body or {}).get("blob")
    if not blob or not isinstance(blob, str):
        raise HTTPException(400, "blob_required")
    return _match(blob)

@router.post('/memory/artifact/correlate')
def memory_artifact_correlate(body: dict):
    a = (body or {}).get("a") or ""
    b = (body or {}).get("b") or ""
    if not isinstance(a, str) or not isinstance(b, str):
        raise HTTPException(400, "invalid_payload")
    return correlate_artifacts(a, b)

__all__ = ['router']
