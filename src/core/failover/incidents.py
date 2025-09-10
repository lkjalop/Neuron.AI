"""Incident logging utilities with rotation & HMAC signing (prototype)."""
from __future__ import annotations
import pathlib, time, json, hmac, hashlib, os
from typing import Iterable, Dict, Any

INCIDENT_LOG = pathlib.Path("artifacts/eval/incidents.log")
MAX_LOG_BYTES = 200_000  # ~200 KB cap before rotation
ROTATE_KEEP = 5
HMAC_KEY_ENV = "INCIDENT_HMAC_KEY"
MAX_LINE_BYTES = 4096


def _hmac_key() -> bytes:
    key = os.getenv(HMAC_KEY_ENV)
    if not key:
        # Derive from ADMIN_API_KEY as fallback (better: separate secret)
        base = os.getenv("ADMIN_API_KEY", "dev-fallback-key")
        key = hashlib.sha256((base+"/incidents").encode()).hexdigest()
    return key.encode()


def _sign(payload: str) -> str:
    return hmac.new(_hmac_key(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _rotate_if_needed():
    if not INCIDENT_LOG.exists():
        return
    if INCIDENT_LOG.stat().st_size < MAX_LOG_BYTES:
        return
    ts = int(time.time())
    rotated = INCIDENT_LOG.with_name(f"incidents.{ts}.log")
    INCIDENT_LOG.rename(rotated)
    # prune old
    logs = sorted(INCIDENT_LOG.parent.glob("incidents.*.log"))
    if len(logs) > ROTATE_KEEP:
        for old in logs[:-ROTATE_KEEP]:
            try: old.unlink()
            except Exception: pass


def append_incident(record: Dict[str, Any]) -> None:
    INCIDENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = dict(record)
    record.setdefault("generated_ts", time.time())
    payload = json.dumps(record, separators=(",", ":"), sort_keys=True)
    if len(payload.encode("utf-8")) > MAX_LINE_BYTES:
        # truncate oversize fields conservatively
        record["truncated"] = True
        for k, v in list(record.items()):
            if isinstance(v, str) and len(v) > 256:
                record[k] = v[:256] + "..."
        payload = json.dumps(record, separators=(",", ":"), sort_keys=True)
    sig = _sign(payload)
    line = json.dumps({"sig": sig, "payload": record})
    _rotate_if_needed()
    INCIDENT_LOG.open("a", encoding="utf-8").write(line + "\n")


def read_incidents(limit: int = 200) -> list[dict[str, Any]]:
    if not INCIDENT_LOG.exists():
        return []
    lines = INCIDENT_LOG.read_text(encoding="utf-8").splitlines()[-limit:]
    out = []
    for ln in lines:
        try:
            wrap = json.loads(ln)
            payload = wrap.get("payload")
            sig = wrap.get("sig")
            if not isinstance(payload, dict) or not isinstance(sig, str):
                continue
            exp = _sign(json.dumps(payload, separators=(",", ":"), sort_keys=True))
            if not hmac.compare_digest(exp, sig):
                payload["sig_valid"] = False
            else:
                payload["sig_valid"] = True
            out.append(payload)
        except Exception:
            continue
    return out

__all__ = ["append_incident", "read_incidents"]
