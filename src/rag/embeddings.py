"""Embedding provider abstraction for RAG corpus.

Allows swapping deterministic pseudo-embedding logic with real model-based
embeddings without changing corpus interface. Providers are simple callables
accepting text or tokens and returning a list[float].
"""
from __future__ import annotations
from typing import Callable, List, Optional, Dict, Any
import hashlib, math, time, threading
try:
    from core.metrics import RETRIEVAL_PROVIDER_FAILOVER_TOTAL  # type: ignore
except Exception:  # pragma: no cover
    RETRIEVAL_PROVIDER_FAILOVER_TOTAL = None  # type: ignore

_PROVIDER: Optional[Callable[[str], List[float]]] = None
_REGISTRY: Dict[str, Dict[str, Any]] = {}
_WARM_CACHE: Dict[str, List[float]] = {}
_PROVIDER_STATS: Dict[str, Dict[str, float]] = {}
_LOCK = threading.Lock()
_DIM = 32


def _hash_embedding(text: str) -> List[float]:
    tokens = [t for t in text.lower().split() if t]
    vec = [0.0] * _DIM
    if not tokens:
        return vec
    for t in tokens[:256]:
        h = int(hashlib.sha256(t.encode('utf-8')).hexdigest()[:8], 16)
        vec[h % _DIM] += 1.0
    norm = math.sqrt(sum(v*v for v in vec)) or 1.0
    return [v / norm for v in vec]


def get_provider() -> Callable[[str], List[float]]:
    return _PROVIDER or _hash_embedding


def set_provider(fn: Callable[[str], List[float]]):
    global _PROVIDER
    _PROVIDER = fn


def register_provider(name: str, fn: Callable[[str], List[float]], health: Optional[Callable[[], bool]] = None):
    """Register a named provider with optional health check callable."""
    _REGISTRY[name] = {"fn": fn, "health": health, "registered_at": time.time()}
    _PROVIDER_STATS.setdefault(name, {"calls": 0.0, "errors": 0.0, "latency_sum": 0.0})
    # If no active provider, set this one
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER = fn


def select_provider(name: str) -> bool:
    rec = _REGISTRY.get(name)
    if not rec:
        return False
    global _PROVIDER
    _PROVIDER = rec["fn"]
    return True


def provider_health() -> Dict[str, Any]:
    out = {}
    for name, rec in _REGISTRY.items():
        ok = None
        h = rec.get("health")
        if callable(h):
            try:
                ok = bool(h())
            except Exception:
                ok = False
        st = _PROVIDER_STATS.get(name, {})
        err_rate = 0.0
        if st.get("calls", 0) > 0:
            err_rate = st.get("errors", 0) / max(1.0, st.get("calls", 0))
        out[name] = {
            "active": (rec["fn"] == _PROVIDER),
            "health": ok,
            "registered_at": rec.get("registered_at"),
            "calls": st.get("calls", 0),
            "errors": st.get("errors", 0),
            "error_rate": round(err_rate, 4),
            "avg_latency_ms": round((st.get("latency_sum", 0)/max(1.0, st.get("calls",0)))*1000, 3),
        }
    return out


def warm_cache(texts: List[str]) -> int:
    provider = get_provider()
    added = 0
    for t in texts:
        key = hashlib.sha256(t.encode('utf-8')).hexdigest()[:16]
        if key not in _WARM_CACHE:
            try:
                _WARM_CACHE[key] = provider(t)
                added += 1
            except Exception:
                continue
    return added


def get_cached(text: str) -> Optional[List[float]]:
    key = hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
    return _WARM_CACHE.get(key)


def embed(text: str) -> List[float]:
    cached = get_cached(text)
    if cached is not None:
        return cached
    prov_fn = get_provider()
    prov_name = None
    for n, rec in _REGISTRY.items():
        if rec["fn"] is prov_fn:
            prov_name = n
            break
    start = time.time()
    try:
        v = prov_fn(text)
        ok = True
        return v
    except Exception:  # pragma: no cover
        ok = False
        v = _hash_embedding(text)  # fallback deterministic
        _failover(prov_name)
        return v
    finally:
        elapsed = time.time() - start
        if prov_name:
            with _LOCK:
                st = _PROVIDER_STATS.setdefault(prov_name, {"calls": 0.0, "errors": 0.0, "latency_sum": 0.0})
                st["calls"] += 1
                if not ok:
                    st["errors"] += 1
                st["latency_sum"] += elapsed


def _failover(current: Optional[str]):  # pragma: no cover - best effort
    if not current:
        return
    # Find next healthy provider with lowest error rate
    best_name = None
    best_err = 1.1
    for n, rec in _REGISTRY.items():
        if n == current:
            continue
        st = _PROVIDER_STATS.get(n, {})
        calls = st.get("calls", 0) or 1.0
        err_rate = st.get("errors", 0) / calls
        h = rec.get("health")
        healthy = True
        if callable(h):
            try:
                healthy = bool(h())
            except Exception:
                healthy = False
        if not healthy:
            continue
        if err_rate < best_err:
            best_err = err_rate
            best_name = n
    if best_name:
        select_provider(best_name)
        try:
            if RETRIEVAL_PROVIDER_FAILOVER_TOTAL is not None:
                RETRIEVAL_PROVIDER_FAILOVER_TOTAL.labels(from_provider=current, to_provider=best_name, reason="error").inc()
        except Exception:
            pass


__all__ = [
    "get_provider",
    "set_provider",
    "register_provider",
    "select_provider",
    "provider_health",
    "warm_cache",
    "get_cached",
    "embed",
    "_hash_embedding",
]
