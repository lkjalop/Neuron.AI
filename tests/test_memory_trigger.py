import asyncio
import pytest
from core.pipeline import Pipeline
from config import runtime_params

class DummyEvent:
    def __init__(self, tenant_id: str, features=None):
        self.tenant_id = tenant_id
        self.features = features or {}
        self.event_id = 'e1'
        self.timestamp = 0.0
        self.metadata = {}

class DummyDetector:
    name = "dummy"
    def __init__(self, anomalies):
        self._anoms = anomalies
    def process(self, ev):
        return list(self._anoms)

@pytest.mark.asyncio
async def test_memory_trigger_low_conf_high_risk(monkeypatch):
    # Configure thresholds
    runtime_params.update_param("memory.trigger.confidence_threshold", 0.6, reason="test", actor="test")
    runtime_params.update_param("memory.trigger.risk_threshold", 50.0, reason="test", actor="test")
    runtime_params.update_param("memory.jobs.active", 5, reason="test", actor="test")

    # Craft anomaly below confidence, above risk threshold
    anomaly = {"score": 0.4, "risk_score": 80.0, "asset_id": "asset123"}

    # Monkeypatch registry.detectors to return dummy
    from core.detect import interface as iface
    monkeypatch.setattr(iface.registry, 'detectors', lambda: [DummyDetector([anomaly])])

    triggered = {}
    async def fake_submit(asset_id, ctx):
        triggered['asset'] = asset_id
        triggered['ctx'] = ctx
        return {"id": "job1"}

    import forensics.memory as mem
    monkeypatch.setattr(mem, 'submit_memory_job', fake_submit)

    p = Pipeline(["t1"])  # auto registers baseline etc., but we patched detectors()

    # Run one loop iteration manually by feeding event and calling private methods
    ev = DummyEvent("t1")
    # Simulate what _loop does for detectors and fusion minimal path
    det_results = {d.name: d.process(ev) for d in iface.registry.detectors()}
    # Bypass fusion arbitrator with pass-through of dummy anomalies
    anomalies = det_results['dummy']
    # Invoke risk overlay (no-op, risk already present) then memory trigger
    await p._apply_risk_overlay(anomalies)
    p._maybe_memory_trigger(anomalies)

    # Allow scheduled task to run
    await asyncio.sleep(0)  # yield once

    assert triggered.get('asset') == 'asset123'
    assert triggered['ctx']['score'] == 0.4
    assert triggered['ctx']['risk'] == 80.0

@pytest.mark.asyncio
async def test_memory_trigger_not_high_risk(monkeypatch):
    runtime_params.update_param("memory.trigger.confidence_threshold", 0.6, reason="test", actor="test")
    runtime_params.update_param("memory.trigger.risk_threshold", 50.0, reason="test", actor="test")
    runtime_params.update_param("memory.jobs.active", 5, reason="test", actor="test")

    anomaly = {"score": 0.4, "risk_score": 40.0, "asset_id": "assetX"}

    from core.detect import interface as iface
    monkeypatch.setattr(iface.registry, 'detectors', lambda: [DummyDetector([anomaly])])

    triggered = {}
    async def fake_submit(asset_id, ctx):
        triggered['asset'] = asset_id
        triggered['ctx'] = ctx
        return {"id": "job1"}

    import forensics.memory as mem
    monkeypatch.setattr(mem, 'submit_memory_job', fake_submit)

    p = Pipeline(["t1"])  # baseline registration etc.
    ev = DummyEvent("t1")
    det_results = {d.name: d.process(ev) for d in iface.registry.detectors()}
    anomalies = det_results['dummy']
    await p._apply_risk_overlay(anomalies)
    p._maybe_memory_trigger(anomalies)
    await asyncio.sleep(0)

    assert 'asset' not in triggered  # no trigger due to insufficient risk
