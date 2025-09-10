import pytest, time
from core.ingest.connectors.persistence import persist_vuln_event
from storage import postgres

@pytest.mark.asyncio
async def test_malformed_events_do_not_raise():
    try:
        await postgres.fetch('SELECT 1 FROM findings LIMIT 1')
    except Exception:
        pytest.skip('findings table missing')
    start = (await postgres.fetch('SELECT count(*) FROM findings'))[0][0]
    ev_bad_meta = {'timestamp': time.time(), 'severity': 20, 'source':'qualys.synthetic', 'metadata': None}
    ev_bad_cve_list = {'timestamp': time.time(), 'severity': 30, 'source':'qualys.synthetic', 'metadata': {'cve_ids':'NOT_A_LIST','host':'asset-bad'}}
    await persist_vuln_event(ev_bad_meta)
    await persist_vuln_event(ev_bad_cve_list)
    end = (await postgres.fetch('SELECT count(*) FROM findings'))[0][0]
    # No new rows expected
    assert end == start
