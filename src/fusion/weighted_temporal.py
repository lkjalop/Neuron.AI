"""Weighted Temporal Fusion Strategy

Combines anomaly scores across detectors using configurable weights and
optional temporal decay to down-weight stale context.
"""
from __future__ import annotations

from typing import List, Dict
import math, time

from detect.orchestrator import Anomaly
from runtime.param_store import get_param
from .strategy import FusionStrategy


class WeightedTemporalFusion:
    name = "weighted_temporal"

    def __init__(self, default_weight: float = 1.0, decay_half_life: float = 300.0):
        self.default_weight = default_weight
        self.half_life = decay_half_life

    def _weight_for(self, detector: str) -> float:
        # param key pattern: fusion.weight.<detector>
        return float(get_param(f"fusion.weight.{detector}", self.default_weight))

    def _decay(self, anomaly: Anomaly) -> float:
        # Exponential decay based on age
        age = max(0.0, time.time() - anomaly.ts)
        if self.half_life <= 0:
            return 1.0
        lam = math.log(2) / self.half_life
        return math.exp(-lam * age)

    def fuse(self, anomalies: List[Anomaly]) -> List[Anomaly]:
        if not anomalies:
            return []
        fused_score = 0.0
        details: Dict[str, float] = {}
        for a in anomalies:
            w = self._weight_for(a.detector)
            d = self._decay(a)
            contrib = a.score * w * d
            fused_score += contrib
            details[a.detector] = contrib
        # Create synthetic fused anomaly
        fused = Anomaly(
            event_id=anomalies[0].event_id,
            detector=self.name,
            score=fused_score,
            reason=f"weighted_sum={fused_score:.2f}",
            ts=time.time(),
            tenant_id=anomalies[0].tenant_id,
            meta={"contributors": details, "count": len(anomalies)},
        )
        return anomalies + [fused]

__all__ = ["WeightedTemporalFusion"]
