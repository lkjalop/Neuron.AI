from __future__ import annotations
import math
from datetime import datetime, timezone, timedelta

from scanner.risk import compute_risk, RiskWeights
from scanner.models import Vulnerability, Finding


NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _vuln(sev: str, exploit=False, epss=None, kev=False, published_days=10):
    return Vulnerability(
        id=f"{sev}-demo-id",
        cve_id=f"CVE-2025-1{published_days:03d}-{sev}",
        aliases=[],
        cvss_base=None,
        cvss_vector=None,
        severity=sev,
        cwe_ids=[],
        published_ts=NOW - timedelta(days=published_days),
        modified_ts=NOW - timedelta(days=published_days),
        exploit_available=exploit,
        epss=epss,
        kev_listed=kev,
        raw_json={},
    )


def _finding(v: Vulnerability):
    return Finding(
        id=f"finding-{v.cve_id}",
        tenant_id="t1",
        vulnerability_id=v.cve_id,
        component_id="comp-1",
        asset_id=None,
        introduced_ts=NOW,
        detected_ts=NOW,
        status="open",
        status_reason=None,
        last_status_change_ts=NOW,
        sla_due_ts=None,
        risk_score=None,
        last_risk_calc_ts=None,
        meta={"criticality": 0.5},
    )


def test_monotonic_severity_scores():
    weights = RiskWeights.from_params({})
    severities = ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    prev = -1.0
    for sev in severities:
        v = _vuln(sev)
        f = _finding(v)
        r = compute_risk(v, f, weights, NOW)
        assert 0.0 <= r["normalized_score"] <= 1.0
        assert r["normalized_score"] >= prev - 1e-9
        prev = r["normalized_score"]


def test_exploit_bonus_deterministic():
    weights = RiskWeights.from_params({})
    v1 = _vuln("HIGH", exploit=False)
    v2 = _vuln("HIGH", exploit=True)
    f1 = _finding(v1)
    f2 = _finding(v2)
    r1 = compute_risk(v1, f1, weights, NOW)
    r2 = compute_risk(v2, f2, weights, NOW)
    assert r2["normalized_score"] >= r1["normalized_score"]
    # Bonus cannot exceed 0.15 absolute per default exploit_bonus_max
    assert r2["normalized_score"] - r1["normalized_score"] <= 0.16


def test_enrichment_weights_applied():
    params = {
        "vuln.risk.weights.epss": 0.2,
        "vuln.risk.weights.kev": 0.15,
        "vuln.risk.epss_threshold": 0.5,
    }
    weights = RiskWeights.from_params(params)
    v = _vuln("MEDIUM", exploit=False, epss=0.9, kev=True)
    f = _finding(v)
    r = compute_risk(v, f, weights, NOW, params=params)
    factors = r["factors"]
    assert factors["epss_component"] > 0
    assert factors["kev_component"] > 0


def test_temporal_decay_half_life():
    params = {"vuln.risk.aging_half_life_days": 30.0}
    weights = RiskWeights.from_params(params)
    recent = _vuln("HIGH", published_days=5)
    old = _vuln("HIGH", published_days=120)
    f1 = _finding(recent)
    f2 = _finding(old)
    r_recent = compute_risk(recent, f1, weights, NOW, params=params)
    r_old = compute_risk(old, f2, weights, NOW, params=params)
    assert r_recent["normalized_score"] >= r_old["normalized_score"]


def test_parameter_robustness_missing_keys():
    params = {"vuln.risk.weights.cvss": 0.4}
    # Should fall back to defaults for other weight keys
    weights = RiskWeights.from_params(params)
    v = _vuln("LOW")
    f = _finding(v)
    r = compute_risk(v, f, weights, NOW, params=params)
    assert 0 <= r["normalized_score"] <= 1.0
