import pytest, time
from core.ingest.connectors.persistence import persist_vuln_event
from storage import postgres

@pytest.mark.asyncio
async def test_idempotent_finding_creation():
    try:
        await postgres.fetch('SELECT 1 FROM findings LIMIT 1')
    except Exception:
        pytest.skip('findings table missing')
    ev = {
        'timestamp': time.time(),
        'severity': 80,
        'source': 'qualys.synthetic',
        'metadata': {
            'cve_ids': ['CVE-TEST-IDEMP'],
            'host': 'asset-idem',
            'exploit_available': True
        }
    }
    await persist_vuln_event(ev)
    await persist_vuln_event(ev)  # second call
    rows = await postgres.fetch("SELECT count(*) FROM findings WHERE cve_id='CVE-TEST-IDEMP' AND asset_id='asset-idem'")
    assert rows[0][0] == 1, 'Duplicate finding row created'
