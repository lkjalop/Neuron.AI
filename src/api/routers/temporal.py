"""Temporal router exposing buffer ingest/status endpoints."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from core.temporal_buffer import ingest as _ingest, status as _status

router = APIRouter(tags=["temporal"]) 

@router.post('/temporal/buffer/ingest')
def temporal_buffer_ingest(body: dict):
    feats = (body or {}).get("features")
    tenant = (body or {}).get("tenant") or "global"
    if not isinstance(feats, dict):
        raise HTTPException(400, "missing_features")
    size = _ingest(tenant, feats)
    return {"status": "ingested", "tenant": tenant, "size": size}

@router.get('/temporal/buffer/status')
def temporal_buffer_status(tenant: str | None = None):
    return _status(tenant)

__all__ = ['router']
