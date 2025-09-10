"""Drift vector computation utilities.

Provides baseline velocity-style drift metrics derived from rolling feature windows.

Functions:
  compute_arrival_velocity(window: list[list[float]]) -> float
  compute_drift_score(window: list[list[float]]) -> float

Arrival velocity: average new findings per bucket (window normalized by bucket count).
Drift score: weighted combination of growth in high severity + exploit flagged counts
             between first half and second half of window.
"""
from __future__ import annotations

from typing import List

def compute_arrival_velocity(window: List[List[float]]) -> float:
    if not window:
        return 0.0
    total_new = sum(vec[0] for vec in window)
    return total_new / len(window)

def compute_drift_score(window: List[List[float]]) -> float:
    n = len(window)
    if n < 4:
        return 0.0
    half = n // 2
    first = window[:half]
    second = window[half:]
    def agg(vs):
        high = sum(v[1] for v in vs)
        exploit = sum(v[2] for v in vs)
        kev = sum(v[3] for v in vs)
        return high, exploit, kev
    h1, e1, k1 = agg(first)
    h2, e2, k2 = agg(second)
    # Simple growth factors
    growth_high = (h2 - h1) / (h1 + 1.0)
    growth_exploit = (e2 - e1) / (e1 + 1.0)
    growth_kev = (k2 - k1) / (k1 + 1.0)
    score = 0.5 * growth_high + 0.3 * growth_exploit + 0.2 * growth_kev
    # Clamp
    if score < -1:
        score = -1
    if score > 5:
        score = 5
    return float(score)

__all__ = ["compute_arrival_velocity", "compute_drift_score"]
