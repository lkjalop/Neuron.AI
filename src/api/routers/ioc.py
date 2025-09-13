from __future__ import annotations

from fastapi import APIRouter, HTTPException
import time, uuid

from core import metrics  # type: ignore

router = APIRouter()

# Shared in-memory stores (import from core.main for test compatibility)
try:
    from core.main import _IOCS as _LEGACY_IOCS  # type: ignore
except Exception:
    _LEGACY_IOCS = []  # type: ignore
try:
    from core.main import _IOCS_STORE as _STORE  # type: ignore
except Exception:
    _STORE = []  # type: ignore


@router.post('/ioc')
def ioc_add(body: dict):
    value = (body or {}).get('value')
    type_ = (body or {}).get('type') or 'generic'
    if not value:
        raise HTTPException(400, 'value_required')
    rec = {"id": uuid.uuid4().hex[:12], "value": value, "type": type_, "added_ts": time.time()}
    # Update both stores to preserve legacy behavior in tests
    _STORE.append(rec)
    # Also update legacy IOC list in core.main for pruning and hit-dedupe tests
    try:
        # Re-import to get current reference in case of reloads
        from core import main as _m  # type: ignore
        if hasattr(_m, '_IOCS') and isinstance(_m._IOCS, list):
            _m._IOCS.append({"value": value, "type": type_, "added_ts": rec["added_ts"]})
    except Exception:
        pass
    try:
        metrics.IOC_INGEST_TOTAL.labels(type=type_).inc()  # type: ignore[attr-defined]
    except Exception:
        pass
    return {"created": rec}


@router.get('/ioc')
def ioc_list(limit: int = 50):
    try:
        limit = max(1, min(200, int(limit)))
    except Exception:
        limit = 50
    return {"items": list(reversed(_STORE))[:limit], "count": len(_STORE)}


@router.get('/ioc/search')
def ioc_search(value: str, limit: int = 50):
    try:
        limit = max(1, min(200, int(limit)))
    except Exception:
        limit = 50
    low = (value or "").lower()
    items = []
    for rec in reversed(_STORE):
        if low in str(rec.get('value', '')).lower():
            items.append(rec)
            if len(items) >= limit:
                break
    return {"items": items, "count": len(items)}
