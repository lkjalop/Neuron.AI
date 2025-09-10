"""Deterministic SNN auto-calibration helper.

Design:
- Pure helper object managing threshold adjustments on discrete intervals.
- Inputs: current totals (events_seen, snn_anoms, baseline_anoms), current threshold, runtime params getter.
- Policy:
    * Only act every `interval` events (events_seen % interval == 0).
    * Compute uplift_ratio = snn_anoms / max(1, baseline_anoms).
    * If snn_anoms == 0: gently decrease threshold (down-step) to increase sensitivity.
    * Else compare to target_ratio with deadband (±10%).
        - Above upper band: increase threshold (reduce anomalies) proportional to deviation capped by max_step.
        - Below lower band: decrease threshold (increase anomalies) proportional to deviation capped.
        - Inside band: no change (stable) – avoids noise.
    * Enforce bounds [min_threshold, max_threshold].

Determinism: given same counts sequence and params, output is stable. No hidden internal state besides last_adjust_event to avoid double adjusting within same interval boundary.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

class ParamGetter(Protocol):
    def __call__(self, key: str) -> float | int | bool | None: ...

@dataclass
class CalibrationDecision:
    changed: bool
    new_threshold: float
    reason: str
    events_seen: int
    snn_anoms: int
    baseline_anoms: int
    uplift_ratio: float

class AutoCalibrator:
    def __init__(self):
        self._last_adjust_event = -1

    def maybe_adjust(self,
                      events_seen: int,
                      snn_anoms: int,
                      baseline_anoms: int,
                      current_threshold: float,
                      get_param: ParamGetter) -> CalibrationDecision:
        try:
            enabled = bool(get_param("snn.auto_cal.enabled"))
        except Exception:
            enabled = False
        if not enabled:
            return CalibrationDecision(False, current_threshold, "disabled", events_seen, snn_anoms, baseline_anoms, 0.0)
        try:
            interval = int(get_param("snn.auto_cal.interval") or 500)
            target_ratio = float(get_param("snn.auto_cal.target_ratio") or 2.0)
            max_step = float(get_param("snn.auto_cal.max_step") or 0.2)
            min_thr = float(get_param("snn.auto_cal.min_threshold") or 0.05)
            max_thr = float(get_param("snn.auto_cal.max_threshold") or 50.0)
        except Exception:
            interval, target_ratio, max_step, min_thr, max_thr = 500, 2.0, 0.2, 0.05, 50.0
        if interval <= 0:
            interval = 1
        if events_seen == 0 or events_seen % interval != 0:
            return CalibrationDecision(False, current_threshold, "no_interval", events_seen, snn_anoms, baseline_anoms, 0.0)
        if events_seen == self._last_adjust_event:
            return CalibrationDecision(False, current_threshold, "already_adjusted", events_seen, snn_anoms, baseline_anoms, 0.0)
        uplift_ratio = snn_anoms / max(1, baseline_anoms if baseline_anoms > 0 else 1)
        new_thr = current_threshold
        reason = "stable"
        deadband_low = target_ratio * 0.9
        deadband_high = target_ratio * 1.1
        if snn_anoms == 0:
            # Encourage more anomalies: lower threshold modestly
            delta = max_step * 0.25
            new_thr = max(min_thr, current_threshold * (1 - delta))
            reason = "zero_anoms_increase_sensitivity"
        elif uplift_ratio > deadband_high:
            # Too many compared to baseline: raise threshold
            overshoot = (uplift_ratio / target_ratio) - 1.0
            adj = min(max_step, overshoot)
            new_thr = min(max_thr, current_threshold * (1 + adj))
            reason = "reduce_uplift"
        elif uplift_ratio < deadband_low:
            undershoot = (target_ratio / max(uplift_ratio, 1e-9)) - 1.0
            adj = min(max_step, undershoot)
            new_thr = max(min_thr, current_threshold * (1 - adj))
            reason = "increase_uplift"
        else:
            # Inside deadband: no change
            return CalibrationDecision(False, current_threshold, "deadband", events_seen, snn_anoms, baseline_anoms, uplift_ratio)
        self._last_adjust_event = events_seen
        changed = abs(new_thr - current_threshold) > 1e-9
        return CalibrationDecision(changed, new_thr, reason, events_seen, snn_anoms, baseline_anoms, uplift_ratio)

__all__ = ["AutoCalibrator", "CalibrationDecision"]
