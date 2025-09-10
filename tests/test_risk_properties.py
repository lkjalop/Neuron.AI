from datetime import datetime, timezone, timedelta
from scanner.risk import compute_risk, RiskWeights
from scanner.models import Vulnerability, Finding
from config.runtime_params import get_param
import math

# Deterministic grid (fallback if Hypothesis not desired); uses a few severities and epss values

NOW = datetime.now(timezone.utc)


def _mk_vuln(cve: str, severity: str, epss: float | None, kev: bool, exploit: bool):
    return Vulnerability(
        id=cve,
        cve_id=cve,
        aliases=[],
        cvss_base=7.0 if severity in ("HIGH", "CRITICAL") else 5.0,
        cvss_vector=None,
        severity=severity,
        cwe_ids=[],
        published_ts=NOW - timedelta(days=30),
        modified_ts=NOW,
        exploit_available=exploit,
        epss=epss,
        kev_listed=kev,
        raw_json={},
    )


def _mk_finding(fid: str, v: Vulnerability):
    return Finding(
        id=fid,
        tenant_id="t",
        vulnerability_id=v.cve_id,
        component_id="c",
        asset_id="a",
        introduced_ts=NOW - timedelta(days=5),
        detected_ts=NOW - timedelta(days=1),
        status="open",
        status_reason=None,
        last_status_change_ts=NOW - timedelta(days=1),
        sla_due_ts=None,
        risk_score=None,
        last_risk_calc_ts=None,
        meta={"criticality": 0.5},
    )


def test_risk_monotonic_severity_and_exploit():
    weights = RiskWeights.from_params(get_param)
    severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    last_score = -1.0
    for sev in severities:
        v = _mk_vuln(f"CVE-test-{sev}", sev, epss=None, kev=False, exploit=False)
        f = _mk_finding(f"finding-{sev}", v)
        r = compute_risk(v, f, weights, NOW, exploit_bonus_max=0.15, params={})
        score = r["normalized_score"]
        assert score >= last_score - 1e-9
        last_score = score
    # Exploit flag should not reduce score
    v_base = _mk_vuln("CVE-test-exploit-base", "HIGH", epss=None, kev=False, exploit=False)
    v_ex = _mk_vuln("CVE-test-exploit-ex", "HIGH", epss=None, kev=False, exploit=True)
    f1 = _mk_finding("finding-base", v_base)
    f2 = _mk_finding("finding-ex", v_ex)
    r1 = compute_risk(v_base, f1, weights, NOW, exploit_bonus_max=0.15, params={})
    r2 = compute_risk(v_ex, f2, weights, NOW, exploit_bonus_max=0.15, params={})
    assert r2["normalized_score"] >= r1["normalized_score"]


def test_epss_threshold_boost_non_decreasing():
    weights = RiskWeights.from_params(get_param)
    thresh = float(get_param("vuln.risk.epss_threshold", 0.5))
    below = max(thresh - 0.1, 0.0)
    above = min(thresh + 0.1, 1.0)
    v_low = _mk_vuln("CVE-epss-low", "MEDIUM", epss=below, kev=False, exploit=False)
    v_high = _mk_vuln("CVE-epss-high", "MEDIUM", epss=above, kev=False, exploit=False)
    f1 = _mk_finding("finding-epss-low", v_low)
    f2 = _mk_finding("finding-epss-high", v_high)
    r1 = compute_risk(v_low, f1, weights, NOW, exploit_bonus_max=0.15, params={"vuln.risk.epss_threshold": thresh})
    r2 = compute_risk(v_high, f2, weights, NOW, exploit_bonus_max=0.15, params={"vuln.risk.epss_threshold": thresh})
    assert r2["normalized_score"] >= r1["normalized_score"]

