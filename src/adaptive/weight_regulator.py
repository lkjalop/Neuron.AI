"""Adaptive Weight Regulator (skeleton).

Adjusts configured detection / fusion weights within safe bounds based on
observed KPI metrics. This scaffolds later closed-loop tuning.

Responsibilities:
  - propose_adjustments(current_weight, observed_metric, target, max_step)
  - apply within min/max bounds (from runtime params) and enforce cooldown

Runtime Params (examples; some may already exist):
  fusion.temporal.tuner.*  (reused for temporal weight concept)

NOTE: This module does not directly mutate runtime params; instead it returns
proposed values so a governance layer can commit them (ensuring audit trail).
"""
from __future__ import annotations

from typing import Optional, Dict, Any
import time
from config.runtime_params import get_param  # type: ignore

_LAST_ADJUST: Dict[str, float] = {}


def _now() -> float:
    return time.time()


def propose_adjustment(key: str, current: float, observed: float, target: float) -> Optional[float]:
    cooldown = float(get_param("fusion.temporal.tuner.cooldown_s") or 30.0)
    max_step_prop = float(get_param("fusion.temporal.tuner.max_step") or 0.25)
    tol = float(get_param("fusion.temporal.tuner.tolerance") or 0.1)
    min_w = float(get_param("fusion.temporal.tuner.min_weight") or 0.0)
    max_w = float(get_param("fusion.temporal.tuner.max_weight") or 2.0)
    now = _now()
    last = _LAST_ADJUST.get(key, 0)
    if now - last < cooldown:
        return None
    # If within tolerance band skip
    if abs(observed - target) <= tol * target:
        return None
    direction = 1.0 if observed < target else -1.0
    step = current * max_step_prop
    if step < 0.001:
        step = 0.001
    proposed = current + direction * step
    proposed = max(min_w, min(max_w, proposed))
    if abs(proposed - current) < 1e-6:
        return None
    _LAST_ADJUST[key] = now
    return round(proposed, 6)


def regulator_state() -> Dict[str, Any]:
    return {"last_adjustments": dict(_LAST_ADJUST)}


__all__ = ["propose_adjustment", "regulator_state"]
