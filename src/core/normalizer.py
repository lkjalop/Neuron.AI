"""Event Normalizer

Converts raw incoming payloads (dict-like) into canonical Event instances.
Features:
 - Tolerant to varied key naming (e.g., ts, time) for timestamp
 - Extracts severity / score synonyms
 - Derives simple numerical features (lengths, counts) for detectors
 - Leaves original raw payload in metadata under 'raw_*' keys

Future extensions:
 - Rich entity extraction (ip/domains/users)
 - PII scrubbing / redaction patterns
 - Feature hashing / embedding hooks
"""
from __future__ import annotations

from typing import Any, Dict, List
import time, re, hashlib, os
from core import metrics

from .event import Event, dict_to_event

_TS_KEYS = ["timestamp", "ts", "time"]
_SEVERITY_KEYS = ["severity", "sev", "score", "risk"]
_TYPE_KEYS = ["event_type", "type", "evt_type", "kind"]
_SOURCE_KEYS = ["source", "src", "origin"]


def _coalesce(d: Dict[str, Any], keys: list[str], default=None):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_DOMAIN_RE = re.compile(r"\b([a-zA-Z0-9-]{1,63}\.)+[a-zA-Z]{2,24}\b")
_HEX_TOKEN_RE = re.compile(r"\b[a-fA-F0-9]{32,64}\b")
_API_KEY_RE = re.compile(r"(?i)(api[_-]?key|secret|token)[=:]\s*([A-Za-z0-9\-_]{16,})")

def _redact(text: str, secrets: List[str]) -> str:
    redacted = text
    for s in secrets:
        redacted = redacted.replace(s, f"<REDACT:{len(s)}>")
    return redacted

def _maybe_hash(val: str) -> str:
    h = hashlib.sha256(val.encode()).hexdigest()[:10]
    return f"hash:{h}"

def normalize_raw_event(raw: Dict[str, Any]) -> Event:
    data = dict(raw)  # shallow copy
    # Pull out canonical fields
    ts = _coalesce(data, _TS_KEYS, time.time())
    etype = _coalesce(data, _TYPE_KEYS, "generic")
    sev = _coalesce(data, _SEVERITY_KEYS, None)
    src = _coalesce(data, _SOURCE_KEYS, None)
    tenant = data.get("tenant") or data.get("tenant_id")

    # Remove consumed keys to prevent duplication noise in metadata
    for k in _TS_KEYS + _SEVERITY_KEYS + _TYPE_KEYS + _SOURCE_KEYS + ["tenant", "tenant_id"]:
        if k in data:
            data.pop(k)

    # Feature derivation (example heuristics)
    features: Dict[str, Any] = {}
    if isinstance(sev, (int, float)):
        features["severity"] = float(sev)
    if isinstance(etype, str):
        features["etype_len"] = len(etype)
    message = None
    if "message" in raw and isinstance(raw["message"], str):
        message = raw["message"]
        features["msg_len"] = len(message)
        features["msg_wc"] = len(message.split())

    # Entity extraction / redaction
    enable_redaction = os.getenv("ENABLE_REDACTION", "true").lower() == "true"
    ips: List[str] = []
    domains: List[str] = []
    secrets_found: List[str] = []
    text_blobs: List[str] = []

    for k in ["message", "url", "path", "command"]:
        v = raw.get(k)
        if isinstance(v, str):
            text_blobs.append(v)

    combined = "\n".join(text_blobs)
    if combined:
        ips = list({m.group(0) for m in _IP_RE.finditer(combined)})[:20]
        domains = list({m.group(0).lower() for m in _DOMAIN_RE.finditer(combined)})[:20]
        secrets_found.extend([m.group(0) for m in _HEX_TOKEN_RE.finditer(combined)])
        secrets_found.extend([m.group(2) for m in _API_KEY_RE.finditer(combined)])

    redactions_applied = 0
    if enable_redaction and combined and secrets_found:
        unique_secrets = list({s for s in secrets_found})[:25]
        redactions_applied = len(unique_secrets)
        # Replace in raw references
        for k in list(raw.keys()):
            v = raw.get(k)
            if isinstance(v, str):
                raw[k] = _redact(v, unique_secrets)
        if message:
            message = _redact(message, unique_secrets)
        try:
            metrics.FUSION_TEMPORAL_TUNER_ADJUSTMENTS.labels(reason="redaction")  # noop reference to ensure metric import not optimized out
        except Exception:
            pass

    if ips:
        features["ip_count"] = len(ips)
    if domains:
        features["domain_count"] = len(domains)
    if redactions_applied:
        features["redactions"] = redactions_applied

    # Size guard: truncate large string values
    max_len = int(os.getenv("NORMALIZER_MAX_STR", 4000))
    truncated = 0
    for k, v in list(raw.items()):
        if isinstance(v, str) and len(v) > max_len:
            truncated += 1
            raw[k] = v[:max_len] + f"<...TRUNCATED {len(v)-max_len} chars hash={hashlib.sha256(v.encode()).hexdigest()[:8]}>"
    if truncated:
        features["truncations"] = truncated
    meta_extra: Dict[str, Any] = {
        "raw_keys": list(raw.keys()),
        **{f"raw_{k}": v for k, v in list(raw.items())[:20]},
    }
    if ips:
        meta_extra["ips"] = ips
    if domains:
        meta_extra["domains"] = domains
    if redactions_applied:
        meta_extra["secrets_redacted"] = redactions_applied
        try:
            if hasattr(metrics, 'NORMALIZER_REDACTIONS_TOTAL'):
                metrics.NORMALIZER_REDACTIONS_TOTAL.labels(reason="secret_pattern").inc()
        except Exception:
            pass

    evt = Event(
        timestamp=float(ts) if ts else time.time(),
        event_type=str(etype),
        severity=float(sev) if isinstance(sev, (int, float)) else None,
        source=src,
        tenant_id=tenant,
        metadata=meta_extra,
        features=features,
    )
    return evt

__all__ = ["normalize_raw_event"]
