"""Central error code registry.

Each entry: code -> {"message": <human>, "http_status": int, "severity": "info|warn|error"}

Provides helper to build standardized error envelopes and record metric emission.
"""
from __future__ import annotations
from typing import Dict, Any
from core import metrics

ERROR_CODES: Dict[str, Dict[str, Any]] = {
    "missing_value": {"message": "Required value missing", "http_status": 400, "severity": "warn"},
    "ioc_revoked": {"message": "IOC value has been revoked", "http_status": 400, "severity": "warn"},
    "missing_pattern": {"message": "Hunt pattern is required", "http_status": 400, "severity": "warn"},
    "validation_disabled": {"message": "Validation endpoint disabled", "http_status": 404, "severity": "info"},
    "normalize_failed": {"message": "Normalization failed", "http_status": 400, "severity": "error"},
    "rate_limited": {"message": "Ingest rate limit exceeded", "http_status": 429, "severity": "warn"},
}

def build_error(code: str, detail: str | None = None) -> Dict[str, Any]:
    meta = ERROR_CODES.get(code, {"message": code, "http_status": 400, "severity": "error"})
    try:
        metrics.ERROR_CODE_TOTAL.labels(code=code).inc()  # type: ignore[attr-defined]
    except Exception:
        pass
    return {
        "error": {
            "code": code,
            "message": meta["message"],
            "detail": detail,
            "severity": meta.get("severity", "error"),
        },
        "status": meta["http_status"],
    }

__all__ = ["ERROR_CODES", "build_error"]