"""Global in-memory anomaly buffer (per-tenant ring buffers).

Lightweight structure to retain recent anomalies for inspection / sampling
without introducing a persistence dependency at Phase 2.
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Deque, Dict, List, Any, Optional
import time, os, json, threading, pathlib

class AnomalyBuffer:
    """In-memory anomaly ring buffers with optional persistent append-only log.

    Persistence is lightweight and line-oriented JSONL to avoid needing a DB in
    early phases. It enables cross-process export (e.g. harness -> exporter) by
    replaying the persisted log if in-memory state is empty.
    Activate by setting env var ANOMALY_PERSIST_PATH (default provided) OR
    disable by setting to empty string."""

    def __init__(self, per_tenant_limit: int = 200, persist_env: str = "ANOMALY_PERSIST_PATH"):
        self._limit = per_tenant_limit
        self._data: Dict[str, Deque[dict]] = defaultdict(lambda: deque(maxlen=self._limit))
        self._persist_path: Optional[pathlib.Path] = None
        path = os.getenv(persist_env, "artifacts/dataset/anomaly_log.jsonl")
        if path:
            self._persist_path = pathlib.Path(path)
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _persist(self, record: dict):  # best-effort
        if not self._persist_path:
            return
        line = json.dumps(record, separators=(",", ":"))
        try:
            with self._lock:
                with self._persist_path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception:
            # Silent failure acceptable at this phase (avoid raising inside hot path)
            pass

    def add(self, tenant: str, anomaly: dict):
        anomaly = dict(anomaly)
        anomaly["stored_ts"] = time.time()
        self._data[tenant].appendleft(anomaly)
        self._persist(anomaly | {"tenant_id": tenant})

    def recent(self, tenant: str, limit: int = 50) -> List[dict]:
        buf = self._data.get(tenant)
        if not buf:
            return []
        return list(list(buf)[:limit])

    def tenants(self) -> List[str]:
        return list(self._data.keys())

    def replay_persisted(self, max_lines: int = 10_000):
        """Replay persisted anomalies (no duplicates) into memory if empty.

        Idempotent best-effort; used by exporter to hydrate memory when running
        in a fresh process."""
        if not self._persist_path or any(self._data.values()) or not self._persist_path.exists():
            return
        try:
            with self._persist_path.open("r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        tenant = rec.get("tenant_id") or rec.get("tenant")
                        if not tenant:
                            continue
                        # remove possible duplicate stored_ts recalculation is fine
                        self._data[tenant].appendleft(rec)
                    except Exception:
                        continue
        except Exception:
            pass

anomaly_buffer = AnomalyBuffer()

__all__ = ["anomaly_buffer", "AnomalyBuffer"]
