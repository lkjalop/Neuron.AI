"""Audit helpers for integration exports."""
from __future__ import annotations
import json, time, os
from pathlib import Path
from .base import ExportResult

AUDIT_FILE = Path("audit/INTEGRATION_EXPORTS.jsonl")

# Ensure directory exists (best-effort)
try:
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

def append_export_audit(name: str, result: ExportResult):
    rec = {
        "ts": time.time(),
        "integration": name,
        "outcome": result.get("outcome"),
        "status_code": result.get("status_code"),
        "latency_s": result.get("latency_s"),
        "count": result.get("count"),
        "error": result.get("error"),
    }
    try:
        with AUDIT_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass
