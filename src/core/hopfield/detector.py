"""Hopfield Detector Wrapper.

Generates anomaly when residual (1 - similarity) exceeds threshold.
Adds fields: hopfield_similarity, hopfield_residual.
"""
from __future__ import annotations
import random, time
from typing import List
from core.detect.interface import DetectionResult, IDetector
from core.event import Event
from .memory import hopfield_instance
from config import runtime_params
from core import metrics

class HopfieldDetector(IDetector):
    name = "hopfield"

    def __init__(self):
        self._last_similarity = 0.0

    def process(self, event: Event) -> List[DetectionResult]:
        # Gating
        try:
            if runtime_params:
                en = runtime_params.get_param("hopfield.enabled")
                if en in {0, False, "0", "false"}:
                    return []
        except Exception:
            pass
        # Create a deterministic pseudo vector from event payload for scaffold
        vec = _vectorize_event(event)
        mem = hopfield_instance()
        reconstructed, sim = mem.associate(vec)
        try:
            metrics.HOPFIELD_RECALL_SCORE.labels(tenant=event.get("tenant_id","unknown")).set(sim)
        except Exception:
            pass
        self._last_similarity = sim
        thr = 0.35
        try:
            if runtime_params:
                t = runtime_params.get_param("hopfield.residual.threshold")
                if isinstance(t,(int,float)):
                    thr = float(t)
        except Exception:
            pass
        residual = 1.0 - sim
        if residual < thr:
            # Optionally store original vector probabilistically to diversify memory
            if random.random() < 0.2:
                mem.store(vec)
            return []
        # Store pattern post anomaly to reinforce recall
        mem.store(vec)
        anomaly: DetectionResult = DetectionResult({
            "detector": self.name,
            "tenant": event.get("tenant_id","unknown"),
            "ts": event.get("ts"),
            "hopfield_similarity": sim,
            "hopfield_residual": residual,
            "residual_threshold": thr,
            "message": f"hopfield_residual_exceeds_threshold:{residual:.3f}>{thr:.3f}",
        })
        return [anomaly]

# --- Simple vectorization scaffold ---

KEYS = ["source","dest","user","action","message"]

def _vectorize_event(ev: Event):  # type: ignore[override]
    import hashlib, math
    # Combine selected keys and hash into dim buckets
    dim = 64
    try:
        from config import runtime_params
        if runtime_params:
            d = runtime_params.get_param("hopfield.dim")
            if isinstance(d,(int,float)):
                dim = int(d)
    except Exception:
        pass
    acc = [0.0]*dim
    blob_parts = []
    for k in KEYS:
        v = ev.get(k)
        if isinstance(v,str):
            blob_parts.append(v)
    blob = "|".join(blob_parts)[:2048]
    # Slide a window hash to distribute
    for i in range(min(len(blob), 256)):
        window = blob[i:i+4]
        h = hashlib.sha256(window.encode()).digest()
        idx = h[0] % dim
        acc[idx] += (h[1] / 255.0)
    # Normalize
    mag = math.sqrt(sum(x*x for x in acc)) or 1.0
    acc = [x/mag for x in acc]
    return acc

__all__ = ["HopfieldDetector"]
