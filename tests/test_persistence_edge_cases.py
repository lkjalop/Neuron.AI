import pytest, time
from core.ingest.connectors.persistence import persist_vuln_event
from storage import postgres

@pytest.mark.asyncio
async def test_persistence_edge_cases():
    try:
        await postgres.fetch('SELECT 1 FROM findings LIMIT 1')
    except Exception:
        pytest.skip('findings table missing')
    base_count = (await postgres.fetch("SELECT count(*) FROM findings"))[0][0]
    # No CVE ids and no plugin id/qid
    ev_no_cve = {'timestamp': time.time(), 'severity': 50, 'source': 'tenable.synthetic', 'metadata': {'host':'asset-edge'}}
    await persist_vuln_event(ev_no_cve)
    after_no_cve = (await postgres.fetch("SELECT count(*) FROM findings"))[0][0]
    assert after_no_cve == base_count, 'Row created without CVE'
    # Multi CVE chooses first
    ev_multi = {'timestamp': time.time(), 'severity': 60, 'source':'qualys.synthetic', 'metadata': {'host':'asset-edge','cve_ids':['CVE-MULTI-1','CVE-MULTI-2']}}
    await persist_vuln_event(ev_multi)
    rows = await postgres.fetch("SELECT cve_id FROM findings WHERE asset_id='asset-edge' AND cve_id LIKE 'CVE-MULTI-%'")
    assert rows and rows[0][0] == 'CVE-MULTI-1'
