import os

from detect.orchestrator import build_default_orchestrator
from ingest.adapters.synthetic import synthetic_stream
from runtime.param_store import set_param


def test_fusion_emits_fused_anomaly(tmp_path, monkeypatch):
    monkeypatch.setenv("ENABLE_FUSION", "true")
    # Ensure weights deterministic
    set_param("fusion.weight.baseline_stats", 1.0, actor="test", reason="init")
    orch = build_default_orchestrator()
    produced_fused = False
    for evt in synthetic_stream(count=80, anomaly_period=25):
        anomalies = orch.process_event(evt)
        if any(a.detector == "weighted_temporal" for a in anomalies):
            produced_fused = True
            break
    assert produced_fused, "Expected fused anomaly when fusion enabled and base anomalies present"


def test_fusion_weight_influence(monkeypatch):
    monkeypatch.setenv("ENABLE_FUSION", "true")
    set_param("fusion.weight.baseline_stats", 0.5, actor="test", reason="low")
    orch_low = build_default_orchestrator()
    scores_low = []
    for evt in synthetic_stream(count=60, anomaly_period=20):
        anomalies = orch_low.process_event(evt)
        fused = [a for a in anomalies if a.detector == "weighted_temporal"]
        if fused:
            scores_low.append(fused[-1].score)
    set_param("fusion.weight.baseline_stats", 2.0, actor="test", reason="raise")
    orch_high = build_default_orchestrator()
    scores_high = []
    for evt in synthetic_stream(count=60, anomaly_period=20):
        anomalies = orch_high.process_event(evt)
        fused = [a for a in anomalies if a.detector == "weighted_temporal"]
        if fused:
            scores_high.append(fused[-1].score)
    # Compare average fused score (should be higher with higher weight)
    if scores_low and scores_high:
        assert sum(scores_high)/len(scores_high) > sum(scores_low)/len(scores_low)
