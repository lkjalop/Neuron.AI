import asyncio
import pytest
from core.pipeline import Pipeline
from core.event import Event
from core.detect.interface import DetectionResult

class DummyEvent(Event):
    def __init__(self, tenant_id: str, metadata: dict, labels: dict | None = None):
        self.event_type = "network_flow"
        self.tenant_id = tenant_id
        self.source = "flow"
        self.metadata = metadata
        self.labels = labels or {}
        self.features = {}
        import time
        self.timestamp = time.time()

class DummyPG:
    def __init__(self):
        self.rows = {"asset-1": {"id": "asset-1", "criticality": 0.9, "external_exposure": True}}
    async def fetch(self, q, *args):  # simplistic pattern match
        if "ANY" in q and args:
            ids = args[0]
            return [self.rows[i] for i in ids if i in self.rows]
        if args:
            aid = args[0]
            return [self.rows[aid]] if aid in self.rows else []
        return []

class DummyVulnStore:
    def __init__(self):
        self.postgres = DummyPG()

@pytest.mark.asyncio
async def test_pipeline_apply_risk_overlay(monkeypatch):
    # Monkeypatch vuln_store
    import storage
    storage.vuln_store = DummyVulnStore()  # type: ignore
    p = Pipeline(["tenantA"])  # don't start full loop
    anomalies = [
        {"asset_id": "asset-1", "risk_score": None, "risk_severity": None},
        {"asset_id": "asset-2", "risk_score": None, "risk_severity": None},
    ]
    await p._apply_risk_overlay(anomalies)  # type: ignore
    enriched = [a for a in anomalies if a.get("asset_id") == "asset-1"][0]
    assert enriched["risk_score"] is not None and enriched["risk_severity"] == "high"
    # asset-2 not present in store remains None
    missing = [a for a in anomalies if a.get("asset_id") == "asset-2"][0]
    assert missing["risk_score"] is None
