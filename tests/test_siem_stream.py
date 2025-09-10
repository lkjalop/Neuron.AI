import pytest, asyncio
from core.ingest.connectors.siem import siem_stream, SIEMConfig


@pytest.mark.asyncio
async def test_siem_stream_basic():
    cfg = SIEMConfig(batch_size=5)
    events = []
    async for ev in siem_stream(cfg):
        events.append(ev)
    # 3 batches * 5 events
    assert len(events) == 15
    assert all(ev['event_type'] == 'siem_event' for ev in events)
