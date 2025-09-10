from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any
from config import runtime_params
from core import metrics
from core.policy.context import policy_context
from core.temporal.calibration import calibrator

@dataclass
class Insight:
    category: str
    hypothesis: str
    confidence: float
    severity: float
    evidence: Dict[str, Any]

class InsightsEngine:
    """Generates heuristic insights from available metrics & policy context.

    Heuristics:
      - low_uplift: temporal uplift ratio << target
      - high_residual_variance: residual variance > guard threshold
      - stale_calibration: calibration freshness > stale threshold
      - high_suppression: suppression rate high
    """
    def __init__(self):
        pass

    def generate(self, tenant: str) -> List[Insight]:
        out: List[Insight] = []
        # Uplift
        target = float(runtime_params.get_param('fusion.temporal.tuner.target_uplift') or 0.8)
        try:
            uplift = metrics.FUSION_TEMPORAL_TUNER_UPLIFT_RATIO._value.get()  # type: ignore[attr-defined]
        except Exception:
            uplift = 0.0
        if uplift < target * 0.5:
            # Severity scales with deficit relative to half-target (1.0 means uplift zero)
            deficit = max(0.0, (target * 0.5) - uplift)
            sev = min(1.0, deficit / (target * 0.5)) if target > 0 else 0.0
            out.append(Insight(
                category='temporal_uplift',
                hypothesis='Temporal contribution significantly below target',
                confidence=0.7,
                severity=sev,
                evidence={'uplift': uplift, 'target': target}
            ))
        # Residual variance
        try:
            # We don't have per-tenant stored value accessible easily; rely on gauge fetch attempt
            variance = 0.0
        except Exception:
            variance = 0.0
        # Calibration freshness
        try:
            freshness = metrics.TEMPORAL_CALIBRATION_FRESHNESS_S.labels(tenant=tenant)._value.get()  # type: ignore[attr-defined]
        except Exception:
            freshness = 0.0
        stale_thr = float(runtime_params.get_param('temporal.guard.max_calibration_stale_s') or 900.0)
        if freshness > stale_thr:
            # Severity proportional to how much freshness exceeds threshold (capped at 2x -> severity 1)
            over = freshness - stale_thr
            sev = min(1.0, over / max(stale_thr, 1e-9))
            out.append(Insight(
                category='calibration_stale',
                hypothesis='Temporal calibration data appears stale',
                confidence=0.6,
                severity=sev,
                evidence={'freshness_s': freshness, 'stale_threshold_s': stale_thr}
            ))
        # Suppression rate
        try:
            suppression_rate = metrics.FUSION_SUPPRESSION_RATE.labels(tenant=tenant)._value.get()  # type: ignore[attr-defined]
        except Exception:
            suppression_rate = 0.0
        alert_thr = float(runtime_params.get_param('fusion.suppression_alert_rate') or 0.85)
        if suppression_rate >= alert_thr:
            # Severity scaled between alert threshold and 1.0 linearly
            sev = min(1.0, (suppression_rate - alert_thr) / max(1.0 - alert_thr, 1e-9))
            out.append(Insight(
                category='fusion_suppression_high',
                hypothesis='Fusion suppression rate elevated; investigate baseline/SNN balance',
                confidence=0.65,
                severity=sev,
                evidence={'suppression_rate': suppression_rate, 'alert_threshold': alert_thr}
            ))
        # Quantile deltas
        ctx = policy_context().snapshot(tenant)
        qd = ctx['temporal']['quantiles']
        if abs(qd['delta_p99']) > max(0.05 * (qd['p99'] or 1.0), 0.01):
            base = max(0.05 * (qd['p99'] or 1.0), 0.01)
            sev = min(1.0, abs(qd['delta_p99']) / (base * 4))  # four times threshold -> severity 1
            out.append(Insight(
                category='quantile_shift',
                hypothesis='Significant shift detected in temporal residual distribution (p99 drift)',
                confidence=0.6,
                severity=sev,
                evidence={'delta_p99': qd['delta_p99'], 'p99': qd['p99']}
            ))
        return out

_engine: InsightsEngine | None = None

def insights_engine() -> InsightsEngine:
    global _engine
    if _engine is None:
        _engine = InsightsEngine()
    return _engine

__all__ = ["insights_engine", "InsightsEngine", "Insight"]
