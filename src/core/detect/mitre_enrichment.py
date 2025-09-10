"""MITRE mapping enrichment module.

Adds candidate MITRE ATT&CK technique IDs to detection records based on detector name
and simple pattern metadata. Future phases may refine using richer context.
"""
from __future__ import annotations
from typing import List, Dict

# Static mapping (seed) - extend as heuristics improve
_DETECTOR_MAPPINGS: Dict[str, List[str]] = {
    "lateral_movement": ["T1021", "T1080"],  # Remote Services, Taint Shared Content
    "persistence": ["T1547", "T1050"],       # Boot or Logon Autostart, New Service
    "beaconing": ["T1071", "T1095"],         # Application Layer Protocol, Non-Application Layer Protocol
    "dns_tunneling": ["T1095", "T1572"],     # Non-Application Layer Protocol, Protocol Tunneling
}

_DEF_FALLBACK = ["T1059"]  # Command and Scripting Interpreter generic


def enrich_with_mitre(anomalies: List[dict]) -> List[dict]:
    """Return new list of anomalies with mitre_techniques field added if absent.

    Idempotent: if an anomaly already has 'mitre_techniques', it is left unchanged.
    """
    out = []
    for a in anomalies:
        if not isinstance(a, dict):
            out.append(a)
            continue
        if "mitre_techniques" in a:
            out.append(a)
            continue
        det = a.get("detector")
        mapped = _DETECTOR_MAPPINGS.get(str(det), _DEF_FALLBACK)
        # lightweight copy to avoid mutating upstream references
        b = dict(a)
        b["mitre_techniques"] = mapped
        out.append(b)
    return out

__all__ = ["enrich_with_mitre"]
