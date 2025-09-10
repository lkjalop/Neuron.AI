"""Runtime Parameter Store

Lightweight, auditable parameter store for dynamic tuning (e.g., fusion
weights, detector thresholds). Designed to keep state local (JSON file)
while emitting audit trail compatible with existing audit log chain.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
import json, threading, time, hashlib, pathlib, os

_PARAM_PATH = pathlib.Path(os.getenv("PARAM_STORE_PATH", "artifacts/param_store.json"))
_AUDIT_PATH = pathlib.Path("audit/param_changes.log")
_LOCK = threading.RLock()
_state: Dict[str, Any] = {}
_loaded = False


def _load():
    global _loaded, _state
    if _loaded:
        return
    if _PARAM_PATH.exists():
        try:
            _state = json.loads(_PARAM_PATH.read_text(encoding="utf-8"))
        except Exception:
            _state = {}
    _loaded = True


def _persist():
    tmp = _PARAM_PATH.with_suffix(".tmp")
    _PARAM_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(_state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(_PARAM_PATH)


def _hash_record(k: str, v: Any) -> str:
    h = hashlib.sha256()
    h.update(k.encode())
    try:
        h.update(json.dumps(v, sort_keys=True).encode())
    except Exception:
        h.update(str(v).encode())
    return h.hexdigest()[:16]


def get_param(key: str, default: Any = None) -> Any:
    with _LOCK:
        _load()
        return _state.get(key, default)


def set_param(key: str, value: Any, *, actor: str = "system", reason: str = "update") -> None:
    with _LOCK:
        _load()
        old = _state.get(key, None)
        if old == value:
            return
        _state[key] = value
        _persist()
        _audit(key, old, value, actor=actor, reason=reason)


def _audit(key: str, old: Any, new: Any, *, actor: str, reason: str):
    _AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": time.time(),
        "key": key,
        "old": old,
        "new": new,
        "actor": actor,
        "reason": reason,
        "hash": _hash_record(key, new),
    }
    with _AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


__all__ = ["get_param", "set_param"]
