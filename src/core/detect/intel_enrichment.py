"""Threat intelligence enrichment stub.

Attaches a synthetic threat_intel object with a heuristic score and tags based on metadata artifacts.
Future implementation will query real IOC / feed correlation and context scoring.
"""
from __future__ import annotations
import math, hashlib
from typing import List

_DEF_TAGS = ["heuristic", "stub"]


def _score_from_artifact(val: str) -> float:
    # Deterministic pseudo score (0.2..0.95) using hash
    h = hashlib.sha256(val.encode()).hexdigest()
    # take first 8 hex chars -> int
    iv = int(h[:8], 16)
    # map to 0..1 then scale
    base = (iv % 10_000) / 10_000.0
    return round(0.2 + base * 0.75, 4)


def enrich_with_intel(anomalies: List[dict]) -> List[dict]:
    out = []
    for a in anomalies:
        if not isinstance(a, dict):
            out.append(a)
            continue
        if "threat_intel" in a:
            out.append(a)
            continue
        meta = a.get("metadata") or {}
        artifact = None
        # choose a stable artifact field
        for k in ("query", "dst", "proc", "user"):
            if k in meta and meta[k]:
                artifact = str(meta[k])
                break
        if not artifact:
            artifact = a.get("reason") or a.get("detector") or "unknown"
        score = _score_from_artifact(artifact)
        tags = list(_DEF_TAGS)
        # heuristic tag injection
        if a.get("detector") == "dns_tunneling":
            tags.append("dns")
        elif a.get("detector") == "lateral_movement":
            tags.append("movement")
        elif a.get("detector") == "persistence":
            tags.append("persistence")
        elif a.get("detector") == "beaconing":
            tags.append("c2")
        b = dict(a)
        b["threat_intel"] = {"score": score, "tags": tags}
        out.append(b)
    return out

__all__ = ["enrich_with_intel"]
