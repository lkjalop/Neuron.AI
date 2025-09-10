import pytest
from core.detect.fusion import FusionArbitrator
from core.detect.interface import DetectionResult
from config import runtime_params
from core import metrics


def dr(det, tenant='t1', eid='e1'):
    return DetectionResult({"detector": det, "tenant": tenant, "event_id": eid})


def strategy_patch(monkeypatch, value):
    monkeypatch.setattr(runtime_params, 'get_param', lambda k: value if k == 'detection.fusion.strategy' else None)


def test_consensus_only_suppresses_unique(monkeypatch):
    strategy_patch(monkeypatch, 'consensus_only')
    arb = FusionArbitrator()
    # Only baseline anomalies -> should suppress them
    fused, meta = arb.fuse({'baseline': [dr('baseline')], 'snn': []})
    assert fused == []
    assert meta['suppressed'] == 1
    # Only snn anomalies
    fused2, meta2 = arb.fuse({'baseline': [], 'snn': [dr('snn')]})
    assert fused2 == []
    assert meta2['suppressed'] == 1
    # Both sides -> union returned
    fused3, meta3 = arb.fuse({'baseline': [dr('baseline')], 'snn': [dr('snn')]})
    assert len(fused3) == 2
    assert meta3['suppressed'] == 0


def test_suppressed_buffer_recent(monkeypatch):
    strategy_patch(monkeypatch, 'baseline_priority')
    arb = FusionArbitrator()
    # Baseline present should suppress snn entries
    fused, meta = arb.fuse({'baseline': [dr('baseline')], 'snn': [dr('snn'), dr('snn', eid='e2')]})
    assert len(fused) == 1
    assert meta['suppressed'] == 2
    recent = arb.recent_suppressed(limit=5)
    assert len(recent) >= 2
    assert all(r['detector'] == 'snn' for r in recent)
    # Metrics counter should have incremented for suppressed snn anomalies
    val = metrics.FUSION_SUPPRESSED_TOTAL.labels(tenant='t1', strategy='baseline_priority', detector='snn')._value.get()  # type: ignore[attr-defined]
    assert val >= 2
