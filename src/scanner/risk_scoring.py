"""Minimal risk scoring for local scanning MVP."""
from __future__ import annotations
from typing import Dict, Any

SEVERITY_BASE = {
    "CRITICAL": 70,
    "HIGH": 55,
    "MEDIUM": 40,
    "LOW": 20,
}

# Output severity thresholds post-adjustment
# (Allows headroom for enrichment factors)
THRESHOLDS = [
    (85, "CRITICAL"),
    (65, "HIGH"),
    (45, "MEDIUM"),
    (0, "LOW"),
]

def compute_risk(match: Dict[str, Any]) -> Dict[str, Any]:
    sev = match.get('severity') or 'LOW'
    base = SEVERITY_BASE.get(sev, 10)
    asset_meta = match.get('asset_metadata') or {}
    crit = 0.0
    try:
        crit = float(asset_meta.get('criticality') or 0.0)
    except Exception:
        crit = 0.0
    # Placeholder exploit fixture bonuses
    kev_bonus = 5 if match.get('kev_listed') else 0
    score = base + kev_bonus + crit * 10
    # Determine final severity bucket
    final_sev = 'LOW'
    for thr, label in THRESHOLDS:
        if score >= thr:
            final_sev = label
            break
    match['risk_score'] = round(score, 2)
    match['risk_severity'] = final_sev
    return match

__all__ = ["compute_risk"]
