import pytest

from core.detect.fusion import FusionArbitrator
from core.detect.interface import DetectionResult


def make_result(det: str, event_id: int):
    return DetectionResult({"detector": det, "event_id": event_id, "tenant": "t1"})


def test_pass_through_strategy(monkeypatch):
    # Force strategy
    from config import runtime_params
    monkeypatch.setattr(runtime_params, 'get_param', lambda k: 'pass_through' if k == 'detection.fusion.strategy' else None)

    arb = FusionArbitrator()
    fused, meta = arb.fuse({
        'baseline': [make_result('baseline', 1)],
        'snn': [make_result('snn', 1), make_result('snn', 2)]
    })
    assert len(fused) == 3
    assert meta['strategy'] == 'pass_through'
    assert meta['suppressed'] == 0


def test_baseline_priority_strategy(monkeypatch):
    from config import runtime_params
    monkeypatch.setattr(runtime_params, 'get_param', lambda k: 'baseline_priority' if k == 'detection.fusion.strategy' else None)

    arb = FusionArbitrator()
    fused, meta = arb.fuse({
        'baseline': [make_result('baseline', 1)],
        'snn': [make_result('snn', 1), make_result('snn', 2)]
    })
    # Only baseline kept
    assert len(fused) == 1
    assert fused[0]['detector'] == 'baseline'
    assert meta['suppressed'] == 2

    # Case where baseline empty -> snn passes
    fused2, meta2 = arb.fuse({
        'baseline': [],
        'snn': [make_result('snn', 3)]
    })
    assert len(fused2) == 1
    assert fused2[0]['detector'] == 'snn'
    assert meta2['suppressed'] == 0
