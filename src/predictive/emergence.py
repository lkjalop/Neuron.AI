"""Emergence probability model stub.

Objective: Provide a placeholder logistic model that estimates probability a vulnerability
will become (or already is) actively exploited / high-priority in the near term.

Inputs (features expected):
  - base_risk (float 0..1)
  - epss (float 0..1)
  - kev_listed (0/1)
  - exploit_available (0/1)
  - age_days (float)
  - reservoir_energy (float)  # derived from reservoir embedding magnitude
  - drift_score (float)       # future: change magnitude in feature space
  - feed_confidence (float 0..1) # aggregated feed trust weighting

Model:
  p = sigmoid(w0 + sum(w_i * feature_i))
Weights are placeholder constants; future: train via offline regression.

API:
  compute_emergence_probability(features: dict[str, float]) -> float
  explain(features) -> dict[str, float]

Integration Plan:
  - Called during risk recompute; result stored in risk_factors["emergence_p"]
  - Upstream pipeline ensures feature defaults if missing.
"""
from __future__ import annotations

import math
from typing import Dict, Any

# Placeholder weights (domain-informed heuristics)
WEIGHTS = {
    "bias": -2.2,
    "base_risk": 1.4,
    "epss": 2.0,
    "kev_listed": 2.2,
    "exploit_available": 1.8,
    "age_days": -0.01,            # older tends to decay slightly
    "reservoir_energy": 0.6,
    "drift_score": 0.9,
    "feed_confidence": 0.5,
}

FEATURE_DEFAULTS = {
    "base_risk": 0.0,
    "epss": 0.0,
    "kev_listed": 0.0,
    "exploit_available": 0.0,
    "age_days": 0.0,
    "reservoir_energy": 0.0,
    "drift_score": 0.0,
    "feed_confidence": 1.0,
}

def _sigmoid(x: float) -> float:
    try:
        if x < -50:
            return 0.0
        if x > 50:
            return 1.0
        return 1.0 / (1.0 + math.exp(-x))
    except Exception:
        return 0.5


def compute_emergence_probability(features: Dict[str, float]) -> float:
    z = WEIGHTS["bias"]
    for k, default in FEATURE_DEFAULTS.items():
        v = float(features.get(k, default) or 0.0)
        w = WEIGHTS.get(k, 0.0)
        z += w * v
    return _sigmoid(z)


def explain(features: Dict[str, float]) -> Dict[str, Any]:
    contributions = {}
    z = WEIGHTS["bias"]
    contributions["bias"] = WEIGHTS["bias"]
    for k, default in FEATURE_DEFAULTS.items():
        v = float(features.get(k, default) or 0.0)
        w = WEIGHTS.get(k, 0.0)
        contrib = w * v
        contributions[k] = contrib
        z += contrib
    contributions["logit_total"] = z
    contributions["probability"] = _sigmoid(z)
    return contributions

__all__ = ["compute_emergence_probability", "explain"]
