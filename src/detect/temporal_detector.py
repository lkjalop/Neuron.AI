"""Temporal Detector Wrapper.

Integrates the temporal transformer scaffold as a detector implementing the
common Detector protocol. Gated by ENABLE_TEMPORAL=true.

Heuristic: when buffer ready, compute deviation score; emit anomaly if score
exceeds dynamic threshold derived from rolling mean + k * rolling std of prior
scores (simple adaptive). Falls back to fixed threshold if insufficient stats.
"""
from __future__ import annotations
import os, time, math
from typing import List, Optional

from core.event import Event
from core import metrics
from core.temporal import transformer
from .orchestrator import Anomaly, Detector


def _enabled() -> bool:
    return os.environ.get("ENABLE_TEMPORAL", "false").lower() in {"1", "true", "yes", "on"}


class TemporalDetector(Detector):
    name = "temporal"
    cost_hint = 0.5  # after baseline, before snn

    def __init__(self, k: float = 2.5):
        if not _enabled():
            raise RuntimeError("TemporalDetector enabled only when ENABLE_TEMPORAL=true")
        self.model = transformer.instance()
        self.k = k
        self.scores: List[float] = []

    def _extract_vec(self, event: Event) -> Optional[List[float]]:
        if not event.features:
            return None
        vals = []
        for v in event.features.values():
            if isinstance(v, (int, float)):
                vals.append(float(v))
        return vals or None

    def evaluate(self, event: Event) -> List[Anomaly]:
        vec = self._extract_vec(event)
        if vec is None:
            return []
        self.model.ingest(vec)
        dev = self.model.deviation()
        tenant = event.tenant_id or 'global'
        metrics.TEMPORAL_ATTENTION_SCORE.labels(tenant=tenant).set(dev)
        if dev == 0.0:
            return []
        self.scores.append(dev)
        if len(self.scores) < 20:  # warm-up
            return []
        mean = sum(self.scores)/len(self.scores)
        var = sum((x-mean)**2 for x in self.scores)/len(self.scores)
        std = math.sqrt(var)
        thresh = mean + self.k * std if std > 0 else mean + 0.25
        anomalies: List[Anomaly] = []
        if dev > thresh:
            anomalies.append(Anomaly(
                event_id=event.event_id,
                detector=self.name,
                score=dev,
                reason=f"dev={dev:.3f} thresh={thresh:.3f}",
                ts=time.time(),
                tenant_id=event.tenant_id,
                meta={"mean": round(mean,3), "std": round(std,3)},
            ))
            metrics.TEMPORAL_ONLY_ANOMALIES_TOTAL.labels(tenant=tenant).inc()
        return anomalies

    def flush(self):
        return None

__all__ = ["TemporalDetector"]
