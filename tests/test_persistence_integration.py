import pytest, asyncio, time
from core.ingest.connectors.persistence import persist_vuln_event
from storage import vuln_store, postgres


@pytest.mark.asyncio
async def test_persist_vuln_event_roundtrip(monkeypatch):
    # Ensure tables exist (assuming migrations applied externally). If not, skip.
    try:
        await postgres.fetch('SELECT 1 FROM findings LIMIT 1')
    except Exception:
        pytest.skip('findings table not available')
    ev = {
        'timestamp': time.time(),
        'severity': 85,
        'source': 'qualys.synthetic',
        'metadata': {
            'cve_ids': ['CVE-2024-9999'],
            'host': 'host-xyz',
            'exploitability': True,
            'patch_available': True
        }
    }
    await persist_vuln_event(ev)
    rows = await postgres.fetch("SELECT * FROM findings WHERE cve_id='CVE-2024-9999'")
    assert rows, 'Finding not persisted'
