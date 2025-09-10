"""Temporal Tuner

Adjusts fusion weights over time based on unique contribution ratios and
precision proxy performance (future expansion). Currently a placeholder
that nudges weights toward detectors with higher unique ratios.
"""
from __future__ import annotations

from runtime.param_store import get_param, set_param


class TemporalTuner:
    def __init__(self, step: float = 0.05, max_weight: float = 5.0, min_weight: float = 0.1):
        self.step = step
        self.max_weight = max_weight
        self.min_weight = min_weight

    def update(self, detector: str, unique_ratio: float):
        key = f"fusion.weight.{detector}"
        current = float(get_param(key, 1.0))
        target = current
        if unique_ratio > 0.3:  # heuristic threshold
            target = min(self.max_weight, current + self.step)
        elif unique_ratio < 0.05:
            target = max(self.min_weight, current - self.step)
        if target != current:
            set_param(key, round(target, 3), actor="tuner", reason=f"unique_ratio={unique_ratio:.3f}")

__all__ = ["TemporalTuner"]
