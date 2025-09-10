"""Baseline Rolling Statistics Detector.

Extracted from orchestrator inline implementation to a dedicated module
for clarity and future extension (e.g., median/MAD, adaptive thresholds,
multivariate expansions).
"""
from __future__ import annotations

from typing import List, Optional
import time

from core.event import Event
from core import metrics
from .orchestrator import Anomaly  # reuse anomaly dataclass


class RollingStatsDetector:
    """Simplistic rolling mean/std deviation anomaly placeholder.

    Parameters:
        window: number of recent values to retain
        threshold: absolute z-score beyond which an event is anomalous

    Notes:
        Warm-up: requires 10 samples before emitting.
        Future: consider replacing std with robust MAD; maintain per-tenant state.
    """
    name = "baseline_stats"
    cost_hint = 0.1

    def __init__(self, window: int = 50, threshold: float = 3.5):
        self.window = window
        self.threshold = threshold
        self.values: List[float] = []

    def evaluate(self, event: Event) -> List[Anomaly]:
        val: Optional[float] = None
        if event.severity is not None:
            val = float(event.severity)
        elif event.features:
            for v in event.features.values():
                if isinstance(v, (int, float)):
                    val = float(v)
                    break
        if val is None:
            return []
        self.values.append(val)
        if len(self.values) > self.window:
            self.values.pop(0)
        if len(self.values) < 10:  # warm-up period
            metrics.DETECTOR_WARMUP_SKIPS.labels(tenant=event.tenant_id or 'global', detector=self.name).inc()
            return []
        mean = sum(self.values)/len(self.values)
        var = sum((x-mean)**2 for x in self.values)/len(self.values)
        std = var ** 0.5
        if std == 0:
            metrics.DETECTOR_MAD_FALLBACK.labels(tenant=event.tenant_id or 'global', detector=self.name).inc()
            return []
        z = (val - mean) / std
        if abs(z) >= self.threshold:
            return [Anomaly(
                event_id=event.event_id,
                detector=self.name,
                score=abs(z),
                reason=f"z={z:.2f} threshold={self.threshold}",
                ts=time.time(),
                tenant_id=event.tenant_id,
            )]
        return []

    def flush(self):  # noqa: D401 simple no-op hook
        return None


__all__ = ["RollingStatsDetector"]
