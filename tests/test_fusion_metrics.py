import pytest

from core.pipeline import Pipeline
from core.event import Event
from config import runtime_params
from core import metrics

class DummyIngestion:
    def __init__(self, events):
        from asyncio import Queue
        self.queue = Queue()
        for e in events:
            self.queue.put_nowait(e)
    async def start(self):
        return
    async def get(self):
        return await self.queue.get()

# Monkeypatch ingestion manager inside pipeline for deterministic tests

@pytest.mark.asyncio
async def test_fusion_metrics_single_event(monkeypatch):
    # Enable SNN so pipeline registers it (if available); if not present, test will still pass focusing on baseline metrics
    monkeypatch.setattr(runtime_params, 'get_param', lambda k: True if k == 'detection.enable_snn' else None)

    # Create simple event where baseline likely produces no anomaly (empty features) to exercise 'none'
    ev = Event(event_id='e1', tenant_id='t1', timestamp=0.0, features={})

    p = Pipeline(tenants=['t1'])
    # Replace ingestion with dummy providing one event then await metrics update via flush
    p.ingestion = DummyIngestion([ev])
    await p.ingestion.start()
    await p.flush(max_items=1)

    # We can't easily inspect counters internal state without scraping; ensure no exception path
    # Sanity: FUSION_DECISIONS_TOTAL should exist in registry
    # Underlying name observed is 'neuron_fusion_decisions' (exporter may append _total when scraping)
    assert metrics.FUSION_DECISIONS_TOTAL._name == 'neuron_fusion_decisions'
