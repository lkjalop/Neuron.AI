"""Cognitive Agent Stub

Purpose: Provide lightweight contextual classification over recent SNN activity
and anomaly patterns without external dependencies. This will later evolve into
richer reasoning (symbolic + retrieval).
"""
from __future__ import annotations
from collections import deque
from typing import Deque, Dict, Any, Optional
import math

class CognitiveAgent:
    def __init__(self, window: int = 40):
        self.window = window
        self.activities: Deque[float] = deque(maxlen=window)
        self.last_prediction: Optional[float] = None

    def record_activity(self, activity: float):
        self.activities.append(activity)

    def classify(self) -> Dict[str, Any]:
        if not self.activities:
            return {"label": "insufficient_data", "confidence": 0.0}
        vals = list(self.activities)
        n = len(vals)
        mean = sum(vals) / n
        var = sum((v - mean) ** 2 for v in vals) / max(1, n - 1)
        std = math.sqrt(var)
        # Simple heuristics
        drift = False
        periodic = False
        burst = False
        if n >= 8:
            first_half = vals[: n // 2]
            second_half = vals[n // 2 :]
            if sum(second_half) / len(second_half) > (sum(first_half) / len(first_half)) * 1.25:
                drift = True
        if n >= 12:
            # Autocorrelation sample at lag ~ n/4
            lag = max(1, n // 4)
            num = sum(vals[i] * vals[i - lag] for i in range(lag, n))
            den = sum(v * v for v in vals)
            ac = num / den if den else 0.0
            if ac > 0.55 and std > 0.01:
                periodic = True
        if std > 1.5 * (mean + 1e-6):
            burst = True
        label = "stable"
        if drift:
            label = "monotonic_drift"
        if periodic:
            label = "periodic_pattern"
        if burst:
            label = "burst_instability"
        confidence = min(1.0, (std / (mean + 1e-6)) if mean > 0 else (std / (std + 1e-6)))
        return {
            "label": label,
            "confidence": round(confidence, 4),
            "std": std,
            "mean": mean,
            "n": n,
            "flags": {"drift": drift, "periodic": periodic, "burst": burst},
        }

__all__ = ["CognitiveAgent"]
