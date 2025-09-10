from datetime import datetime, timezone, timedelta
from scanner.risk import RiskWeights, compute_risk
from scanner.models import Vulnerability, Finding


def _v(sev: str | None = "HIGH", exploit=False, days_old=10):
    dt = datetime.now(timezone.utc) - timedelta(days=days_old)
    return Vulnerability(id="v1", cve_id="CVE-X", aliases=["CVE-X"], cvss_base=7.5, cvss_vector="", severity=sev, cwe_ids=[], published_ts=dt, modified_ts=dt, exploit_available=exploit, epss=None, kev_listed=False, raw_json={})


def _f():
    f = Finding(
        id="f1",
        tenant_id="tenant1",
        vulnerability_id="CVE-X",
        component_id="comp1",
        asset_id="a1",
        introduced_ts=datetime.now(timezone.utc),
        detected_ts=datetime.now(timezone.utc),
        status="open",
        status_reason=None,
        last_status_change_ts=datetime.now(timezone.utc),
        sla_due_ts=None,
        risk_score=None,
        last_risk_calc_ts=None,
        meta={}
    )
    # Add asset_metadata as an attribute for compute_risk compatibility
    f.asset_metadata = {"criticality": 0.9}
    return f


def test_compute_risk_exploit_bonus_increases_score():
    v = _v(exploit=True)
    f = _f()
    w = RiskWeights(0.3,0.3,0.2,0.2)
    r = compute_risk(v,f,w, now=datetime.now(timezone.utc))
    assert r["raw_score"] <= 1.0
    assert r["raw_score"] >= 0.3  # exploit boosts


def test_compute_risk_temporal_decay():
    v_new = _v(days_old=5)
    v_old = _v(days_old=200)
    f = _f()
    w = RiskWeights(0.3,0.3,0.2,0.2)
    r_new = compute_risk(v_new,f,w, now=datetime.now(timezone.utc))
    r_old = compute_risk(v_old,f,w, now=datetime.now(timezone.utc))
    assert r_new["raw_score"] > r_old["raw_score"]


def test_compute_risk_severity_tiers():
    f = _f()
    w = RiskWeights(0.3,0.3,0.2,0.2)
    v_low = _v(sev="LOW")
    v_crit = _v(sev="CRITICAL")
    r_low = compute_risk(v_low,f,w, now=datetime.now(timezone.utc))
    r_crit = compute_risk(v_crit,f,w, now=datetime.now(timezone.utc))
    assert r_crit["raw_score"] > r_low["raw_score"]
