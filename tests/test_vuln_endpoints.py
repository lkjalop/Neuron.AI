import pytest, time
from fastapi.testclient import TestClient
from core.main import app

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('ADMIN_API_KEY', 'adminkey')
    return TestClient(app)

def _seed_vuln_and_findings():
    # Directly manipulate in-memory structures (acceptable for unit tests)
    from scanner.scanner_agent import _VULNS, _FINDINGS, Vulnerability, Finding  # type: ignore
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    # Clear existing
    _VULNS.clear(); _FINDINGS.clear()
    v1 = Vulnerability(id='v1', cve_id='CVE-TEST-0001', aliases=[], cvss_base=None, cvss_vector=None, severity='high', cwe_ids=[], published_ts=None, modified_ts=None, exploit_available=True, epss=0.9, kev_listed=True, raw_json={})
    v2 = Vulnerability(id='v2', cve_id='CVE-TEST-0002', aliases=[], cvss_base=None, cvss_vector=None, severity='medium', cwe_ids=[], published_ts=None, modified_ts=None, exploit_available=False, epss=None, kev_listed=False, raw_json={})
    _VULNS[v1.id] = v1; _VULNS[v2.id] = v2
    f1 = Finding(id='f1', tenant_id='t1', vulnerability_id=v1.cve_id, component_id='compA', asset_id=None,
                 introduced_ts=now, detected_ts=now, status='open', status_reason=None,
                 last_status_change_ts=now, sla_due_ts=None, risk_score=0.75, last_risk_calc_ts=now, meta={})
    f2 = Finding(id='f2', tenant_id='t1', vulnerability_id=v2.cve_id, component_id='compB', asset_id=None,
                 introduced_ts=now, detected_ts=now, status='fixed', status_reason=None,
                 last_status_change_ts=now, sla_due_ts=None, risk_score=0.20, last_risk_calc_ts=now, meta={})
    _FINDINGS[f1.id] = f1; _FINDINGS[f2.id] = f2

@pytest.mark.asyncio
async def test_list_vulnerabilities_filter(client):
    _seed_vuln_and_findings()
    r = client.get('/vuln/vulnerabilities?exploit_available=true', headers={'x-api-key':'adminkey'})
    assert r.status_code == 200
    data = r.json()
    assert data['count'] == 1
    assert data['items'][0]['cve_id'] == 'CVE-TEST-0001'
    r2 = client.get('/vuln/vulnerabilities?kev_listed=true', headers={'x-api-key':'adminkey'})
    assert r2.status_code == 200
    assert r2.json()['count'] == 1

@pytest.mark.asyncio
async def test_list_findings_filter_status(client):
    _seed_vuln_and_findings()
    r = client.get('/vuln/findings?status=open', headers={'x-api-key':'adminkey'})
    assert r.status_code == 200
    data = r.json()
    assert data['count'] == 1 and data['items'][0]['status'] == 'open'

