import pytest
from fastapi.testclient import TestClient
from core.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('ADMIN_API_KEY', 'adminkey')
    return TestClient(app)


def _seed_vulns():
    from scanner.scanner_agent import _VULNS, Vulnerability  # type: ignore
    # Clear and seed two vulns: one with EPSS+KEV, one without
    _VULNS.clear()
    v1 = Vulnerability(id='v1', cve_id='CVE-EC-0001', aliases=[], cvss_base=None, cvss_vector=None,
                       severity='high', cwe_ids=[], published_ts=None, modified_ts=None,
                       exploit_available=True, epss=0.42, kev_listed=True, raw_json={})
    v2 = Vulnerability(id='v2', cve_id='CVE-EC-0002', aliases=[], cvss_base=None, cvss_vector=None,
                       severity='low', cwe_ids=[], published_ts=None, modified_ts=None,
                       exploit_available=False, epss=None, kev_listed=False, raw_json={})
    _VULNS[v1.id] = v1
    _VULNS[v2.id] = v2


def test_enrichment_coverage_endpoint_shape(client):
    _seed_vulns()
    r = client.get('/vuln/enrichment/coverage', headers={'x-api-key': 'adminkey'})
    assert r.status_code == 200
    data = r.json()
    # Keys present
    for k in ("total", "epss_count", "kev_count", "epss_pct", "kev_pct"):
        assert k in data
    # Basic math checks
    assert data['total'] == 2
    assert data['epss_count'] == 1
    assert data['kev_count'] == 1
    assert pytest.approx(data['epss_pct'], rel=1e-6) == 50.0
    assert pytest.approx(data['kev_pct'], rel=1e-6) == 50.0
