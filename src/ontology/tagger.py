"""Ontology Tagger (CVE/CWE Keyword Heuristic)

Provides a lightweight, deterministic tagging helper for anomaly feature maps.

Function:
    tag_anomaly(features: dict, *, store: dict, max_tags: int = 5) -> list[str]

Logic:
  - Lowercase feature keys & stringified values.
  - For each CVE entry keywords list, if any keyword substring appears in either a key or str(value), tag with CVE and its CWE.
  - Deduplicate while preserving order of first match (CVE then CWE).
  - Stop when max_tags reached.

Future:
  - Expand to support semantic embeddings & TF-IDF weighting.
  - Add scoring metadata (e.g., keyword hit counts) for ranking.
"""
from __future__ import annotations

from typing import Dict, List


def tag_anomaly(features: Dict, *, store: Dict, max_tags: int = 5) -> List[str]:
    tags: List[str] = []
    seen = set()
    # Flatten feature space to lower strings
    kv_pairs = []
    for k, v in features.items():
        try:
            kv_pairs.append((str(k).lower(), str(v).lower()))
        except Exception:
            continue
    for cve, meta in store.get('entries', {}).items():
        kws = meta.get('keywords') or []
        matched = False
        for kw in kws:
            kw_l = str(kw).lower()
            for k_str, v_str in kv_pairs:
                if kw_l in k_str or kw_l in v_str:
                    matched = True
                    break
            if matched:
                break
        if matched:
            if cve not in seen:
                tags.append(cve)
                seen.add(cve)
            cwe = meta.get('cwe')
            if cwe and cwe not in seen:
                tags.append(cwe)
                seen.add(cwe)
        if len(tags) >= max_tags:
            break
    return tags

__all__ = ["tag_anomaly"]
