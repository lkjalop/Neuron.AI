"""Canonical feature registry.

Defines an ordered feature list and vectorization helper to produce dense
vectors aligned with the sequence buffer expectations.
"""
from __future__ import annotations

from typing import List, Dict

_FEATURES: List[str] = [
    "cpu",
    "mem",
]

_FILL_VALUE = 0.0


def feature_order() -> List[str]:
    return list(_FEATURES)


def to_vector(feature_map: Dict[str, float]) -> List[float]:
    vec: List[float] = []
    for name in _FEATURES:
        v = feature_map.get(name, _FILL_VALUE)
        try:
            v = float(v)
        except Exception:
            v = _FILL_VALUE
        vec.append(v)
    return vec


__all__ = ["feature_order", "to_vector"]
