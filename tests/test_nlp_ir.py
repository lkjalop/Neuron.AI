import pytest
from nlp.translator import translate


def _clause(ir, t):
    return [c for c in ir['clauses'] if c.get('type') == t]


def test_multi_severity_in_clause():
    q = "critical high vulnerabilities"
    ir = translate(q)
    sev = _clause(ir, 'severity')
    assert sev, "severity clause missing"
    c = sev[0]
    assert c['operator'] == 'in'
    assert set(c['values']) == {"CRITICAL", "HIGH"}


def test_exploit_flag():
    ir = translate("show exploited critical vulns")
    ex = _clause(ir, 'exploit_status')
    assert ex and ex[0]['value'] is True


def test_age_parsing():
    ir = translate("older than 30 days high vulns")
    age = _clause(ir, 'age')
    assert age and age[0]['value'] == 30 and age[0]['operator'] == '>'


def test_limit_and_sort():
    ir = translate("top 15 highest severity findings")
    lim = _clause(ir, 'limit')
    sort = _clause(ir, 'sort')
    assert lim and lim[0]['value'] == 15
    assert sort and sort[0]['field'] in {'severity', 'age_days'}
    assert ir['domain'] == 'findings'


def test_cve_extraction_single():
    ir = translate("details for CVE-2024-1234 please")
    cves = _clause(ir, 'cve_id')
    assert cves and cves[0]['operator'] == 'equals' and cves[0]['value'] == 'CVE-2024-1234'


def test_cve_extraction_multi():
    ir = translate("compare CVE-2024-1111 CVE-2023-9999 and high vulns")
    cves = _clause(ir, 'cve_id')
    assert cves and cves[0]['operator'] == 'in'
    assert set(cves[0]['values']) == {'CVE-2024-1111', 'CVE-2023-9999'}


def test_asset_filters():
    ir = translate("critical asset:web01 host:db02")
    assets = _clause(ir, 'asset')
    assert assets and assets[0]['operator'] == 'in'
    assert set(assets[0]['values']) == {'web01', 'db02'}


def test_confidence_low_fallback_tokens():
    ir = translate("nonsenseword anotherjunk token")
    assert ir['meta']['confidence'] < 0.4
    # translator itself doesn't set fallback_used unless endpoint; ensure high unparsed tokens
    assert len(ir['meta']['unparsed_tokens']) >= 2


def test_confidence_high_when_many_semantic_tokens():
    ir = translate("critical high exploit older than 10 days top 5 sort by severity")
    assert ir['meta']['confidence'] >= 0.4
