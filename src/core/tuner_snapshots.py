"""Snapshot ledger for runtime parameter approvals & rollbacks.

Format: JSONL entries under artifacts/params/param_snapshots.log
Entry schema:
{
  "audit_id": str,  # short hex
  "param": str,
  "old": any,
  "new": any,
  "actor": str,
  "reason": str,
  "ts": float
}

Provides helper APIs used by tuner endpoints.
"""
from __future__ import annotations
import os, json, time, threading, hashlib, typing as t
from pathlib import Path

_SNAPSHOT_DIR = Path("artifacts/params")
_SNAPSHOT_FILE = _SNAPSHOT_DIR / "param_snapshots.log"
_LOCK = threading.RLock()

class SnapshotEntry(t.TypedDict, total=False):
    audit_id: str
    param: str
    old: t.Any
    new: t.Any
    actor: str
    reason: str
    ts: float

ALLOWED_PARAMS = {
    "fusion.weighted_sum.suppress_threshold": (0.0, 1.0),
    "detection.fusion.strategy": None,  # strategy strings
}

_DEF_MAX = 1000  # max entries to retain in memory listing

def _ensure_dir():
    _SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

def _hash_id(param: str, old: t.Any, new: t.Any, ts: float) -> str:
    h = hashlib.sha1()
    h.update(f"{param}|{old}|{new}|{ts}".encode())
    return h.hexdigest()[:12]

def record_snapshot(param: str, old: t.Any, new: t.Any, actor: str, reason: str) -> SnapshotEntry:
    """Persist a snapshot and return the entry."""
    if not param:
        raise ValueError("param_required")
    ts = time.time()
    audit_id = _hash_id(param, old, new, ts)
    entry: SnapshotEntry = {
        "audit_id": audit_id,
        "param": param,
        "old": old,
        "new": new,
        "actor": actor,
        "reason": reason,
        "ts": ts,
    }
    line = json.dumps(entry, separators=(",", ":"))
    with _LOCK:
        _ensure_dir()
        with open(_SNAPSHOT_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    return entry

def list_snapshots(limit: int = 100) -> list[SnapshotEntry]:
    limit = max(1, min(_DEF_MAX, int(limit)))
    if not _SNAPSHOT_FILE.exists():
        return []
    out: list[SnapshotEntry] = []
    with _LOCK:
        for line in reversed(_SNAPSHOT_FILE.read_text(encoding="utf-8").splitlines()[-limit:]):
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    # newest first
    out.sort(key=lambda e: e.get("ts", 0), reverse=True)
    return out[:limit]

def find_snapshot(audit_id: str) -> SnapshotEntry | None:
    if not _SNAPSHOT_FILE.exists():
        return None
    with _LOCK:
        for line in reversed(_SNAPSHOT_FILE.read_text(encoding="utf-8").splitlines()):
            try:
                js = json.loads(line)
                if js.get("audit_id") == audit_id:
                    return js
            except Exception:
                continue
    return None

def latest_value(param: str) -> t.Any | None:
    if not _SNAPSHOT_FILE.exists():
        return None
    with _LOCK:
        for line in reversed(_SNAPSHOT_FILE.read_text(encoding="utf-8").splitlines()):
            try:
                js = json.loads(line)
                if js.get("param") == param:
                    return js.get("new")
            except Exception:
                continue
    return None

__all__ = [
    "record_snapshot",
    "list_snapshots",
    "find_snapshot",
    "latest_value",
    "ALLOWED_PARAMS",
]
