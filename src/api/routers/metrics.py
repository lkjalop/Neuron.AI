"""Metrics router exposing Prometheus /metrics with conditional auth and throttling.

This mirrors the logic previously in core.main but keeps it modular for symmetry
with other routers. It depends on core.main's auth utilities when available.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, Request
import os

try:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest  # type: ignore
except Exception:  # pragma: no cover
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"  # type: ignore
    def generate_latest():  # type: ignore
        return b""

# Best-effort import of shared auth + rate-limiter helpers from core.main
try:  # pragma: no cover - path can shift in some envs; fallbacks provided below
    from core.main import require_predict_api_key  # type: ignore
except Exception:
    def require_predict_api_key(*args, **kwargs):  # type: ignore
        # When keys are configured, absence of this import would be unexpected; allow then rely on local checks
        return True
try:
    from core.main import _token_bucket_allow  # type: ignore
except Exception:
    # Minimal local token-bucket fallback (per-process best-effort)
    import time as _time
    _BUCKETS: dict[str, dict[str, float]] = {}
    def _bucket_params(scope: str) -> tuple[float, float]:
        up = scope.upper()
        try:
            rps = float(os.getenv(f"{up}_RATELIMIT_RPS", "5"))
        except Exception:
            rps = 5.0
        try:
            burst = float(os.getenv(f"{up}_RATELIMIT_BURST", "5"))
        except Exception:
            burst = 5.0
        rps = max(0.1, min(1000.0, rps))
        burst = max(1.0, min(1000.0, burst))
        return rps, burst
    def _token_bucket_allow(key: str, scope: str) -> bool:  # type: ignore
        now = _time.time()
        rps, burst = _bucket_params(scope)
        st = _BUCKETS.setdefault(f"{scope}:{key}", {"tokens": burst, "last": now})
        elapsed = max(0.0, now - st["last"]) 
        st["tokens"] = min(burst, st["tokens"] + elapsed * rps)
        st["last"] = now
        if st["tokens"] >= 1.0:
            st["tokens"] -= 1.0
            return True
        return False


router = APIRouter(tags=["metrics"]) 


@router.get("/metrics")
def metrics_endpoint(request: Request):
    """Expose Prometheus metrics with conditional auth and throttling.

    Behavior:
      - If ADMIN_API_KEY or PREDICT_API_KEY configured, require header via require_predict_api_key.
      - If not configured, allow access but still apply token-bucket throttling using a public key bucket.
    """
    admin = os.getenv("ADMIN_API_KEY")
    predict = os.getenv("PREDICT_API_KEY")
    # Enforce auth when keys configured
    if admin or predict:
        # Delegate to shared dependency (will raise on failure)
        require_predict_api_key(request)
    else:
        # Apply public bucket throttling to avoid scrape overload
        if not _token_bucket_allow("public", "predict"):
            raise HTTPException(429, "rate_limited")
    try:
        data = generate_latest()  # type: ignore
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"metrics_error:{e}")


__all__ = ["router"]
