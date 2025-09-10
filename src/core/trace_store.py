"""In-memory anomaly trace store.

Captures per-event detector outcomes + fusion metadata for analyst / evaluation traceability.

Record structure:
  {
    'event_id': str,
    'tenant': str,
    'timestamp': float,
    'detectors': [ { 'name': str, 'fired': bool, 'anomalies': List[DetectionResult] } ],
    'fusion': { 'strategy': str, 'suppressed': int, 'fused_count': int },
  }

Size bounded via deque maxlen (default 500). Not durable; future persistence may move to Redis/Postgres.
"""
from __future__ import annotations

from collections import deque
from typing import Deque, List, Dict, Any, Optional
import time


class TraceStore:
    def __init__(self, maxlen: int = 500):
        self._records: Deque[Dict[str, Any]] = deque(maxlen=maxlen)
        self._index: Dict[str, Dict[str, Any]] = {}

    def add(self, record: Dict[str, Any]):
        ev_id = record.get("event_id")
        if ev_id:
            # if already exists, replace (latest wins)
            if ev_id in self._index:
                # remove old entry by filtering (cheap given small window)
                # rebuild deque without old record
                old = self._index[ev_id]
                self._records = deque([r for r in self._records if r is not old], maxlen=self._records.maxlen)
            self._index[ev_id] = record
        self._records.append(record)
        # if eviction occurred, repair index
        if len(self._records) == self._records.maxlen:
            # prune any stale index keys (rare path)
            current_ids = {r.get('event_id') for r in self._records}
            stale = [k for k in self._index if k not in current_ids]
            for k in stale:
                self._index.pop(k, None)

    def get(self, event_id: str) -> Optional[Dict[str, Any]]:
        return self._index.get(event_id)

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        if limit <= 0:
            return []
        return list(list(self._records)[-limit:])


_trace_store: TraceStore | None = None


def traces() -> TraceStore:
    global _trace_store
    if _trace_store is None:
        _trace_store = TraceStore()
    return _trace_store


__all__ = ["TraceStore", "traces"]