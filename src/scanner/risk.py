from __future__ import annotations
from dataclasses import asdict
from typing import Dict, Any
from datetime import datetime, timezone

from .models import Vulnerability, Finding

# Contract:
# compute_risk returns a dict with fields: raw_score, normalized_score (0-1), factors (detailed), severity_label
# Inputs: vulnerability + finding context + runtime weights + now reference time.

SEVERITY_ORDER = ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]

class RiskWeights:
    def __init__(self, expl: float, asset: float, temporal: float, vuln: float):
        self.exploitability = expl
        self.asset_value = asset
        self.temporal_decay = temporal
        self.vulnerability_severity = vuln

    @classmethod
    def from_params(cls, params: Dict[str, Any] | Any):  # params may be mapping or callable (get_param)
        def _lookup(key: str, default: float) -> float:
            try:
                if callable(params):
                    val = params(key)
                else:
                    val = params.get(key, default)
                if val is None:
                    return default
                return float(val)
            except Exception:
                return default
        # Support both legacy and new schema key names (cvss/exploit/exposure/age)
        expl = _lookup("vuln.risk.weights.exploitability", _lookup("vuln.risk.weights.exploit", 0.3))
        asset = _lookup("vuln.risk.weights.asset_value", _lookup("vuln.risk.weights.exposure", 0.3))
        temporal = _lookup("vuln.risk.weights.temporal_decay", _lookup("vuln.risk.weights.age", 0.2))
        vuln = _lookup("vuln.risk.weights.vuln_severity", _lookup("vuln.risk.weights.cvss", 0.2))
        return cls(expl, asset, temporal, vuln)

    def total(self) -> float:
        return self.exploitability + self.asset_value + self.temporal_decay + self.vulnerability_severity


def _severity_score(sev: str | None) -> float:
    if not sev:
        return 0.0
    sev = sev.upper()
    try:
        return SEVERITY_ORDER.index(sev) / (len(SEVERITY_ORDER) - 1)
    except ValueError:
        return 0.0


def compute_risk(v: Vulnerability, finding: Finding | None, weights: RiskWeights, now: datetime | None = None, exploit_bonus_max: float = 0.15, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Expanded risk model:
      - Asset criticality weighting (already present)
      - EPSS boost: configurable weight if EPSS > threshold
      - KEV boost: configurable weight if KEV listed
      - Aging decay: configurable half-life (default 365 days)
      - All weights tunable via runtime params
    """
    now = now or datetime.now(timezone.utc)
    params = params or {}
    # Tunable weights (may be gated by enrichment flag)
    enrichment_enabled = bool(int(params.get("vuln.enrichment.apply", 1))) if params else True
    epss_weight = float(params.get("vuln.risk.weights.epss", 0.15)) if enrichment_enabled else 0.0
    kev_weight = float(params.get("vuln.risk.weights.kev", 0.1)) if enrichment_enabled else 0.0
    epss_threshold = float(params.get("vuln.risk.epss_threshold", 0.5))
    aging_half_life = float(params.get("vuln.risk.aging_half_life_days", 365.0))

    sev_component = _severity_score(v.severity)
    exploit_component = 1.0 if v.exploit_available else 0.0

    age_days = None
    if v.published_ts:
        age_days = max(0.0, (now - v.published_ts).total_seconds() / 86400.0)
    # Aging decay: exponential half-life
    temporal_component = 1.0
    if age_days is not None and aging_half_life > 0:
        temporal_component = max(0.0, 0.5 ** (age_days / aging_half_life))

    asset_value_component = 0.5
    if finding and isinstance(finding.asset_metadata, dict):
        asset_value_component = float(finding.asset_metadata.get("criticality", 0.5))

    # EPSS boost
    epss_component = 0.0
    if enrichment_enabled and v.epss is not None and v.epss >= epss_threshold:
        epss_component = epss_weight * v.epss

    # KEV boost
    kev_component = kev_weight if enrichment_enabled and getattr(v, "kev_listed", False) else 0.0

    # Weighted sum
    # Only add enrichment weights to denominator if enabled to keep normalization stable when disabled
    total_w = weights.total() + (epss_weight + kev_weight if enrichment_enabled else 0.0) or 1.0
    numerator = (
        sev_component * weights.vulnerability_severity +
        exploit_component * weights.exploitability +
        temporal_component * weights.temporal_decay +
        asset_value_component * weights.asset_value +
        epss_component +
        kev_component
    )
    raw = numerator / total_w

    # Exploit bonus (capped). Enforce upper bound hard clamp (<=0.16) for stability across model revisions.
    if v.exploit_available:
        # External callers may pass a larger exploit_bonus_max; clamp defensively.
        bonus_cap = min(exploit_bonus_max, 0.16)
        raw = min(1.0, raw + min(bonus_cap, bonus_cap * raw))

    severity_label = (
        "CRITICAL" if raw >= 0.85 else
        "HIGH" if raw >= 0.65 else
        "MEDIUM" if raw >= 0.4 else
        "LOW" if raw > 0 else
        "NONE"
    )

    # Contribution shares (pre exploit bonus & multipliers) for later aggregation/visualization
    contrib_shares = {}
    if numerator > 0:
        contrib_shares = {
            "severity": (sev_component * weights.vulnerability_severity) / numerator,
            "exploitability": (exploit_component * weights.exploitability) / numerator,
            "temporal": (temporal_component * weights.temporal_decay) / numerator,
            "asset_value": (asset_value_component * weights.asset_value) / numerator,
            "epss": (epss_component) / numerator,
            "kev": (kev_component) / numerator,
        }
    return {
        "raw_score": raw,
        "normalized_score": raw,
        "severity_label": severity_label,
        "factors": {
            "severity_component": sev_component,
            "exploit_component": exploit_component,
            "temporal_component": temporal_component,
            "asset_value_component": asset_value_component,
            "epss_component": epss_component,
            "kev_component": kev_component,
            "age_days": age_days,
            "weights": {
                "exploitability": weights.exploitability,
                "asset_value": weights.asset_value,
                "temporal_decay": weights.temporal_decay,
                "vuln_severity": weights.vulnerability_severity,
                "epss": epss_weight,
                "kev": kev_weight,
            },
            "aging_half_life": aging_half_life,
            "epss_threshold": epss_threshold,
            "enrichment_enabled": enrichment_enabled,
        },
        "contributions": {
            "shares": contrib_shares,
            "numerator": numerator,
            "total_weight": total_w,
        },
        "vulnerability": v.cve_id,
        "finding_id": finding.id if finding else None,
    }

__all__ = ["RiskWeights", "compute_risk"]
