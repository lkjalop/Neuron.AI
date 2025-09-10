"""SNN Detector integration.

Environment gating: ENABLE_SNN=true to activate.
Uses core.snn.model.build_backend to obtain backend implementation (proto / lif etc.).

Encoding Strategy (simple placeholder):
 - Extract up to N numeric feature values from event.features (stable key sort)
 - Map value -> spike rate (min-max over rolling window) then sample binary spike presence for single timestep window_size (T).
This remains intentionally lightweight; future rate / latency encoders can replace _encode().
"""
from __future__ import annotations
import os, time, random, hashlib
from typing import List, Optional

from core.event import Event
from core import metrics
from core.snn import model as snn_model
from .orchestrator import Anomaly, Detector


def _enabled() -> bool:
    return os.environ.get("ENABLE_SNN", "false").lower() in {"1", "true", "on", "yes"}


class SNNDetector(Detector):
    name = "snn"
    cost_hint = 0.6  # after baseline + iforest

    def __init__(self, window: int = 8, max_features: int = 8):
        if not _enabled():
            raise RuntimeError("SNNDetector only enabled when ENABLE_SNN=true")
        self.window = window
        self.max_features = max_features
        self.backend = snn_model.build_backend()
        self._feat_keys: List[str] = []
        self._min: Optional[List[float]] = None
        self._max: Optional[List[float]] = None
        # Determinism controls
        self._deterministic = os.environ.get("SNN_DETERMINISTIC", "false").lower() in {"1", "true", "yes", "on"}
        self._base_seed = int(os.environ.get("SNN_SEED", "1337"))

    def _extract_numeric(self, event: Event) -> Optional[List[float]]:
        if not event.features:
            return None
        numeric = {k: v for k, v in event.features.items() if isinstance(v, (int, float))}
        if not numeric:
            return None
        if not self._feat_keys:
            self._feat_keys = sorted(numeric.keys())[: self.max_features]
        # require stable features
        missing = [k for k in self._feat_keys if k not in numeric]
        if missing:
            return None
        return [float(numeric[k]) for k in self._feat_keys]

    def _update_minmax(self, vec: List[float]):
        if self._min is None:
            self._min = list(vec)
            self._max = list(vec)
            return
        for i, v in enumerate(vec):
            if v < self._min[i]:
                self._min[i] = v
            if v > self._max[i]:
                self._max[i] = v

    def _encode(self, vec: List[float], event_id: str) -> List[List[int]]:
        # Normalize 0..1 using running min/max; guard zero range
        assert self._min and self._max
        norm = []
        for i, v in enumerate(vec):
            rng = (self._max[i] - self._min[i]) or 1.0
            norm.append((v - self._min[i]) / rng)
        # Generate spike train T x F using Bernoulli(norm_i)
        spikes: List[List[int]] = []
        if self._deterministic:
            # Derive per-event seed from base + stable hash of event_id
            h = hashlib.sha256(event_id.encode("utf-8")).digest()
            seed_offset = int.from_bytes(h[:4], 'little')
            rnd = random.Random(self._base_seed + seed_offset)
            rand_fn = rnd.random
        else:
            rand_fn = random.random
        for _ in range(self.window):
            step = [1 if rand_fn() < p else 0 for p in norm]
            spikes.append(step)
        return spikes

    def evaluate(self, event: Event) -> List[Anomaly]:
        vec = self._extract_numeric(event)
        if vec is None:
            return []
        self._update_minmax(vec)
        if self._min is None or self._max is None:
            return []
        t_start = time.perf_counter()
        spikes = self._encode(vec, event.event_id)
        score = self.backend.forward(spikes)
        latency = time.perf_counter() - t_start
        metrics.SNN_INFERENCE_LATENCY.observe(latency)
        # Basic spike density + activity metrics
        tenant = event.tenant_id or 'global'
        total_spikes = sum(sum(step) for step in spikes)
        density = total_spikes / max(1, (self.window * len(spikes[0])))
        metrics.SNN_SPIKE_DENSITY.labels(tenant=tenant).set(density)
        metrics.SNN_ACTIVITY.labels(tenant=tenant).set(score)
        # Simple anomaly decision: score relative to density threshold
        # Placeholder heuristic: if density > 0.7 and score high or density <0.05 and score high (unexpected activation)
        anomalies: List[Anomaly] = []
        if (density > 0.7 and score > len(spikes[0]) * 0.75) or (density < 0.05 and score > 1.5):
            anomalies.append(Anomaly(
                event_id=event.event_id,
                detector=self.name,
                score=float(score),
                reason=f"snn_score={score:.2f} density={density:.2f}",
                ts=time.time(),
                tenant_id=event.tenant_id,
                meta={"density": round(density, 4)},
            ))
        return anomalies

    def flush(self):  # no-op for now
        return None


__all__ = ["SNNDetector"]
