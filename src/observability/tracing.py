"""Lightweight structured tracing instrumentation.

Provides a minimal span context manager to record timing, nesting, and tags.
In-memory ring buffer retained for recent spans; future work could export to OTLP.
"""
from __future__ import annotations
import time, threading, os, json, uuid, math
from contextlib import contextmanager
from typing import Dict, Any, List, Optional

_MAX_SPANS = 5000
_lock = threading.Lock()
_spans: List[Dict[str, Any]] = []
_local = threading.local()
_EXPORT_FILE = os.path.join("artifacts", "spans", "otlp_spans.jsonl")
_LAST_EXPORTED_INDEX = 0  # monotonic position

def _ensure_export_dir():
    d = os.path.dirname(_EXPORT_FILE)
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass

def export_enabled() -> bool:
    return os.getenv("TRACE_OTLP_EXPORT", "0").lower() in {"1", "true", "yes", "on"}

def flush_export(max_batch: int = 1000) -> int:
    """Flush newly recorded spans to JSONL file in simplified OTLP-like schema.

    Schema fields: trace_id, span_id, parent_id, name, start_ns, end_ns, attributes (tags), status.
    Returns number of spans written in this flush.
    Safe to call frequently; writes only new spans since last flush.
    """
    global _LAST_EXPORTED_INDEX
    if not export_enabled():
        return 0
    with _lock:
        if _LAST_EXPORTED_INDEX >= len(_spans):
            return 0
        batch = _spans[_LAST_EXPORTED_INDEX: _LAST_EXPORTED_INDEX + max_batch]
        _LAST_EXPORTED_INDEX += len(batch)
    if not batch:
        return 0
    _ensure_export_dir()
    try:
        with open(_EXPORT_FILE, "a", encoding="utf-8") as fh:
            for s in batch:
                start_s = s.get('start', 0.0)
                dur_ms = s.get('duration_ms', 0.0)
                end_s = start_s + (dur_ms / 1000.0)
                rec = {
                    "trace_id": f"{int(start_s*1e6):032x}",  # deterministic-ish
                    "span_id": f"{s.get('id'):016x}",
                    "parent_id": f"{s.get('parent'):016x}" if s.get('parent') else None,
                    "name": s.get('name'),
                    "start_ns": int(math.floor(start_s * 1e9)),
                    "end_ns": int(math.floor(end_s * 1e9)),
                    "attributes": s.get('tags') or {},
                    "status": "error" if s.get('error') else "ok",
                    "error": s.get('error'),
                }
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
    except Exception:
        return 0
    return len(batch)


def _now() -> float:
    return time.time()


def get_spans(limit: int = 200) -> List[Dict[str, Any]]:
    with _lock:
        return list(_spans[-limit:])


def clear():  # pragma: no cover
    with _lock:
        _spans.clear()


@contextmanager
def span(name: str, **tags: Any):
    start = _now()
    parent_id: Optional[int] = getattr(_local, 'current_span_id', None)
    span_id = int(start * 1e6) ^ hash(name) & 0xFFFFFFFF
    # push
    _local.current_span_id = span_id
    error: Optional[str] = None
    try:
        yield
    except Exception as e:  # pragma: no cover (error path rare in tests)
        error = repr(e)
        raise
    finally:
        dur = _now() - start
        record = {
            'id': span_id,
            'parent': parent_id,
            'name': name,
            'start': start,
            'duration_ms': round(dur * 1000, 3),
            'tags': tags,
            'error': error,
        }
        with _lock:
            _spans.append(record)
            if len(_spans) > _MAX_SPANS:
                del _spans[0: len(_spans) - _MAX_SPANS]
        # pop
        _local.current_span_id = parent_id

__all__ = ["span", "get_spans", "clear"]
__all__ += ["flush_export", "export_enabled"]
