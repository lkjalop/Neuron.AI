from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any
from core.temporal.calibration import calibrator
from core import metrics

@dataclass
class TemporalQuantileDelta:
    p90_delta: float
    p99_delta: float
    prev_p90: float
    prev_p99: float
    curr_p90: float
    curr_p99: float

class PolicyContextProvider:
    """Provides enriched context for policy/agent decisions.

    Tracks last seen quantiles per tenant to compute deltas and surfaces
    temporal gating ratio (count of gated temporal anomalies / total temporal anomalies)
    if available via metrics (best-effort).
    """
    def __init__(self):
        self._last_quantiles: Dict[str, tuple[float,float]] = {}
        self._temporal_gate_counts: Dict[str, Dict[str, int]] = {}

    def update_temporal_gate(self, tenant: str, gated: bool):
        cnt = self._temporal_gate_counts.setdefault(tenant, {"gated":0, "total":0})
        cnt["total"] += 1
        if gated:
            cnt["gated"] += 1

    def temporal_gating_ratio(self, tenant: str) -> float:
        cnt = self._temporal_gate_counts.get(tenant)
        if not cnt or cnt["total"] == 0:
            return 0.0
        return cnt["gated"] / max(1, cnt["total"])

    def quantile_deltas(self, tenant: str) -> TemporalQuantileDelta:
        cal = calibrator()
        _p50,_p90,_p99 = cal.quantiles(tenant)
        prev = self._last_quantiles.get(tenant, (0.0,0.0))
        prev_p90, prev_p99 = prev
        delta = TemporalQuantileDelta(
            p90_delta=_p90 - prev_p90,
            p99_delta=_p99 - prev_p99,
            prev_p90=prev_p90,
            prev_p99=prev_p99,
            curr_p90=_p90,
            curr_p99=_p99,
        )
        self._last_quantiles[tenant] = (_p90,_p99)
        return delta

    def snapshot(self, tenant: str) -> Dict[str, Any]:
        d = self.quantile_deltas(tenant)
        return {
            'temporal': {
                'quantiles': {
                    'p90': d.curr_p90,
                    'p99': d.curr_p99,
                    'delta_p90': d.p90_delta,
                    'delta_p99': d.p99_delta,
                },
                'gating_ratio': self.temporal_gating_ratio(tenant),
            }
        }

_policy_ctx: PolicyContextProvider | None = None

def policy_context() -> PolicyContextProvider:
    global _policy_ctx
    if _policy_ctx is None:
        _policy_ctx = PolicyContextProvider()
    return _policy_ctx

__all__ = ["policy_context", "PolicyContextProvider"]
