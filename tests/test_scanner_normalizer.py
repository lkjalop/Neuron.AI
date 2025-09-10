from scanner.normalizer import normalize_nvd, normalize_osv, merge_vulnerabilities
from scanner.models import Vulnerability


def test_normalize_nvd_basic():
    item = {"cve": {"id": "CVE-2024-0001"}, "metrics": {}, "published": "2024-01-02T00:00:00Z"}
    v = normalize_nvd(item)
    assert v.cve_id == "CVE-2024-0001"
    assert v.published_ts is not None


def test_normalize_osv_basic():
    entry = {"id": "OSV-1", "aliases": ["CVE-2024-0002"], "published": "2024-02-02T00:00:00Z"}
    v = normalize_osv(entry)
    assert v.cve_id == "CVE-2024-0002"
    assert "CVE-2024-0002" in v.aliases


def test_merge_vulnerabilities_prefers_first_cvss():
    a = Vulnerability(id="1", cve_id="CVE-1", aliases=["CVE-1"], cvss_base=7.5, cvss_vector="V3", severity="HIGH", cwe_ids=[], published_ts=None, modified_ts=None, exploit_available=False, epss=None, kev_listed=False, raw_json={})
    b = Vulnerability(id="2", cve_id="CVE-1", aliases=["CVE-1","ALIAS"], cvss_base=None, cvss_vector=None, severity=None, cwe_ids=[], published_ts=None, modified_ts=None, exploit_available=False, epss=None, kev_listed=False, raw_json={})
    merged = merge_vulnerabilities([a,b])
    assert merged["CVE-1"].cvss_base == 7.5
    assert "ALIAS" in merged["CVE-1"].aliases
