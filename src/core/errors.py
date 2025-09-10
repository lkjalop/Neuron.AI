"""Unified error formatting utilities and domain error codes.

Streaming transport decision: SSE (Server-Sent Events) chosen for guided and ELI5 streaming.
This module centralizes error response construction to keep frontend contract stable.

Error envelope shape:
{
  "error": {
      "code": "STRING_CONSTANT",
      "message": "Human readable",
      "retry_after_s": <int|null>,
      "meta": { ... optional extra fields ... }
  }
}

Usage:
    from core.errors import raise_error
    raise_error("RATE_LIMIT_HOURLY_CAP", "Hourly cap reached", retry_after_s=3600)

FastAPI Integration:
    In routers: return JSONResponse(error_response(...), status_code=429)
    Or raise HTTPException(status_code, detail=error_response(...)["error"]) and register exception handler.

Simpler path here: provide helper that raises HTTPException with packed detail.

Codes reserved:
  - RATE_LIMIT_HOURLY_CAP
  - COOLDOWN_ACTIVE
  - VALIDATION_ERROR
  - NOT_FOUND
  - INTERNAL_ERROR
  - PERMISSION_DENIED
  - CONFLICT
  - STREAM_ABORTED
  - SNAPSHOT_NOT_FOUND
  - ROLLBACK_UNAVAILABLE
  - DIFF_BASE_MISSING
  - DIFF_TARGET_MISSING
  - PATCH_APPLY_FAILED
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import HTTPException

# Exportable set for documentation generation
ERROR_CODES: set[str] = {
    "RATE_LIMIT_HOURLY_CAP",
    "COOLDOWN_ACTIVE",
    "VALIDATION_ERROR",
    "NOT_FOUND",
    "INTERNAL_ERROR",
    "PERMISSION_DENIED",
    "CONFLICT",
    "STREAM_ABORTED",
    "SNAPSHOT_NOT_FOUND",
    "ROLLBACK_UNAVAILABLE",
    "DIFF_BASE_MISSING",
    "DIFF_TARGET_MISSING",
    "PATCH_APPLY_FAILED",
}


def error_payload(code: str, message: str, *, retry_after_s: Optional[int] = None, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if code not in ERROR_CODES:
        # Allow extension without requiring code registration: still include but mark unknown
        # (frontend should surface gracefully).
        pass
    payload = {
        "error": {
            "code": code,
            "message": message,
            "retry_after_s": retry_after_s,
            "meta": meta or {},
        }
    }
    return payload


def raise_error(code: str, message: str, *, status_code: int = 400, retry_after_s: Optional[int] = None, meta: Optional[Dict[str, Any]] = None) -> None:
    raise HTTPException(status_code=status_code, detail=error_payload(code, message, retry_after_s=retry_after_s, meta=meta)["error"])  # type: ignore[arg-type]


class DomainError(Exception):
    """Generic domain error captured and converted to unified envelope."""
    def __init__(self, code: str, message: str, *, retry_after_s: Optional[int] = None, meta: Optional[Dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.retry_after_s = retry_after_s
        self.meta = meta or {}
        super().__init__(message)


def domain_error_to_response(exc: DomainError) -> Dict[str, Any]:
    return error_payload(exc.code, exc.message, retry_after_s=exc.retry_after_s, meta=exc.meta)
