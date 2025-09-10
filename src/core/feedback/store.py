"""Feedback ingestion append-only log with hash chain (A18).

Each record: {
  ts: float (server time),
  query: str,
  retrieved_chunk_ids: List[str or tuple],
  relevance: int|str,
  notes: str,
  provenance_hashes: List[str],
  prev: sha256(previous_line) or 64 zeros for first,
  hash: sha256(current_line_json)
}

Stored at artifacts/feedback/feedback_log.jsonl. Safe to call concurrently (thread lock).
"""
from __future__ import annotations
import threading, json, pathlib, hashlib, time, typing as t

_LOCK = threading.Lock()
_FEEDBACK_DIR = pathlib.Path("artifacts/feedback")
_LOG_FILE = _FEEDBACK_DIR / "feedback_log.jsonl"
_HEAD_FILE = _FEEDBACK_DIR / "feedback_log.head"


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def append_feedback(rec: dict) -> dict:
    """Append feedback record; returns stored record with chain metadata."""
    with _LOCK:
        _FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
        prev = "0" * 64
        if _HEAD_FILE.exists():
            try:
                prev = _HEAD_FILE.read_text(encoding="utf-8").strip() or prev
            except Exception:
                pass
        stored = {
            "ts": time.time(),
            **rec,
        }
        line_obj = {"prev": prev, "rec": stored}
        line = json.dumps(line_obj, separators=(",", ":"))
        h = _sha256(line)
        line_obj["hash"] = h
        with _LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line_obj) + "\n")
        try:
            _HEAD_FILE.write_text(h, encoding="utf-8")
        except Exception:
            pass
        return line_obj


def recent(n: int = 50) -> list[dict]:
    if not _LOG_FILE.exists():
        return []
    out: list[dict] = []
    try:
        with _LOG_FILE.open("r", encoding="utf-8") as f:
            for line in f.readlines()[-n:]:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return out

__all__ = ["append_feedback", "recent"]
