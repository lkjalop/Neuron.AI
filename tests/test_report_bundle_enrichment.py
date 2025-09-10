import json
import pytest
from pathlib import Path


@pytest.mark.asyncio
async def test_report_bundle_includes_enrichment(monkeypatch):
    # Seed scanner vulns so fallback path is deterministic
    from scanner.scanner_agent import _VULNS, Vulnerability  # type: ignore
    _VULNS.clear()
    v = Vulnerability(id='vA', cve_id='CVE-BUNDLE-1', aliases=[], cvss_base=None, cvss_vector=None,
                      severity='medium', cwe_ids=[], published_ts=None, modified_ts=None,
                      exploit_available=False, epss=0.1, kev_listed=False, raw_json={})
    _VULNS[v.id] = v
    # Build bundle (HTML off for speed)
    from reports.unified_pipeline import build_report_bundle  # type: ignore
    res = await build_report_bundle(include_html=False, include_diff=False)
    assert 'json' in res and res['json']
    path = Path(res['json'])
    assert path.exists(), 'bundle.json not written'
    bundle = json.loads(path.read_text(encoding='utf-8'))
    assert 'enrichment_coverage' in bundle
    cov = bundle['enrichment_coverage'] or {}
    for k in ("total", "epss_count", "kev_count", "epss_pct", "kev_pct"):
        assert k in cov
    assert cov['total'] >= 1
    # EPSS count should be at least 1 due to seeded vuln
    assert cov['epss_count'] >= 1
