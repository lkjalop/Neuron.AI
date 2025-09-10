"""Deterministic enrichment fixtures for EPSS & KEV (Batch 7/8).

Provides lightweight, offline-friendly enrichment lookups to support tests
and local development when external enrichment feeds are unavailable.

Contract:
 - get_epss_scores(cve_ids) -> dict[cve_id, probability]
 - get_kev_set() -> set[cve_id]

Determinism Strategy:
 - EPSS probability derived from stable hash of CVE id (first 2 hex chars)
   mapped into [0,1] with 4 decimal precision.
 - KEV membership: include CVEs whose hash nibble modulo 13 == 0 (low density).

Gate via runtime param `vuln.enrichment.apply`; callers decide whether to use.
"""
from __future__ import annotations

import hashlib
from typing import Iterable, Dict, Set


def _hash_nibbles(cve_id: str) -> int:
    h = hashlib.sha256(cve_id.encode("utf-8")).hexdigest()
    return int(h[:2], 16)


def get_epss_scores(cve_ids: Iterable[str]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for cid in cve_ids:
        try:
            n = _hash_nibbles(cid)
            # Map 0-255 -> 0-1; add slight non-linearity to spread middle region
            p = (n / 255.0) ** 1.05
            out[cid] = round(p, 4)
        except Exception:
            continue
    return out


def get_kev_set(cve_ids: Iterable[str]) -> Set[str]:
    kev: Set[str] = set()
    for cid in cve_ids:
        try:
            n = _hash_nibbles(cid)
            if n % 13 == 0:  # sparse selection
                kev.add(cid)
        except Exception:
            continue
    return kev


__all__ = ["get_epss_scores", "get_kev_set"]