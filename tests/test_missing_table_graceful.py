import pytest, time
from core.ingest.connectors.persistence import persist_vuln_event
from storage import vuln_store

class DummyError(Exception):
    pass

@pytest.mark.asyncio
async def test_missing_table_handling(monkeypatch):
    # Monkeypatch vuln_store.postgres.execute to raise on insert
    orig_exec = vuln_store.postgres.execute
    async def boom(*a, **k):
        if isinstance(a[0], str) and 'INSERT INTO findings' in a[0]:
            raise DummyError('relation findings does not exist')
        return await orig_exec(*a, **k)
    monkeypatch.setattr(vuln_store.postgres, 'execute', boom)
    ev = {'timestamp': time.time(), 'severity': 75, 'source':'qualys.synthetic', 'metadata': {'cve_ids':['CVE-MISS-TABLE'],'host':'asset-miss'}}
    # Should not raise
    await persist_vuln_event(ev)
