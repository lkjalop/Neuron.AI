"""JSONL Ingestion Adapter

Streams events from a JSON Lines file. Supports:
 - Tail-like follow (optional)
 - Bounded batch read
 - Graceful parse errors (counted via metrics if available)

Each line should contain a JSON object mapping convertible to Event.
"""
from __future__ import annotations

from typing import Iterator, Optional, Dict, Any
import json, time, os, pathlib

from core.event import dict_to_event, Event
from core import metrics  # assuming metrics module exists


def stream_jsonl(path: str | os.PathLike, *, follow: bool = False, sleep: float = 0.25, stop_after: Optional[int] = None) -> Iterator[Event]:
    count = 0
    p = pathlib.Path(path)
    with p.open('r', encoding='utf-8') as f:
        while True:
            pos = f.tell()
            line = f.readline()
            if not line:
                if follow:
                    time.sleep(sleep)
                    f.seek(pos)
                    continue
                break
            line = line.strip()
            if not line:
                continue
            try:
                obj: Dict[str, Any] = json.loads(line)
                evt = dict_to_event(obj)
                yield evt
                count += 1
                if stop_after is not None and count >= stop_after:
                    break
            except Exception:
                try:
                    metrics.INGEST_ERRORS_TOTAL.labels(error_type="jsonl_parse").inc()
                except Exception:
                    pass
                continue

__all__ = ["stream_jsonl"]
