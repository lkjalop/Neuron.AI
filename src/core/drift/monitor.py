"""Drift monitoring stub computing Population Stability Index (PSI).

PSI compares a reference distribution (baseline window) to a current window for each numeric feature:
  PSI = sum( (pi - qi) * ln(pi / qi) ) over bins i
Where pi = proportion in reference bin i, qi = proportion in current bin i.

Implementation Notes:
- We auto-create equal-width bins from reference min/max (default 10 bins) if dynamic bins not provided.
- Zero-count bins get a small epsilon (1e-6) to avoid division-by-zero and extreme log terms.
- Reference window collected first (warmup); once size >= ref_min, freeze reference histogram.
- Current window uses sliding buffer; on each compute() we update FEATURE_PSI gauge for features recorded.
- Lightweight: O(F * B) per compute where F ~ number of numeric features and B bins.

Future Enhancements:
- Quantile-based bins for robustness
- Adaptive reference refresh with exponential decay
- Alerting thresholds integrated into governance
"""
from __future__ import annotations

from collections import deque
from typing import Dict, List, Deque, Tuple
import math

from core.event import Event
from core import metrics

_EPS = 1e-6

class FeatureWindow:
    def __init__(self, maxlen: int):
        self.values: Deque[float] = deque(maxlen=maxlen)

    def add(self, v: float):
        self.values.append(v)

    def snapshot(self) -> List[float]:
        return list(self.values)

class DriftMonitor:
    def __init__(self, reference_size: int = 500, window_size: int = 500, bins: int = 10):
        self.reference_size = reference_size
        self.window_size = window_size
        self.bins = bins
        # per tenant -> feature -> FeatureWindow
        self._reference: Dict[str, Dict[str, FeatureWindow]] = {}
        self._current: Dict[str, Dict[str, FeatureWindow]] = {}
        self._frozen: Dict[str, Dict[str, List[float]]] = {}  # frozen reference values

    def record(self, event: Event):
        tenant = event.tenant_id or "default"
        ref_feat = self._reference.setdefault(tenant, {})
        cur_feat = self._current.setdefault(tenant, {})
        frozen_feat = self._frozen.setdefault(tenant, {})
        for k, v in event.features.items():
            if not isinstance(v, (int, float)):
                continue
            # reference collection until frozen
            if k not in frozen_feat:
                fw = ref_feat.setdefault(k, FeatureWindow(self.reference_size))
                fw.add(float(v))
                if len(fw.values) >= self.reference_size:
                    frozen_feat[k] = fw.snapshot()
            # current always collects
            cw = cur_feat.setdefault(k, FeatureWindow(self.window_size))
            cw.add(float(v))

    def compute(self):
        # compute PSI for tenants/features with frozen reference
        for tenant, frozen_feat in self._frozen.items():
            cur_feat = self._current.get(tenant, {})
            for feature, ref_values in frozen_feat.items():
                current_values = cur_feat.get(feature).snapshot() if feature in cur_feat else []
                if not current_values:
                    continue
                psi = self._psi(ref_values, current_values)
                try:
                    metrics.FEATURE_PSI.labels(tenant=tenant, feature=feature).set(psi)  # type: ignore[attr-defined]
                except Exception:
                    pass

    def _psi(self, ref: List[float], cur: List[float]) -> float:
        if not ref or not cur:
            return 0.0
        rmin, rmax = min(ref), max(ref)
        if rmin == rmax:
            return 0.0  # no variance; drift unidentifiable with PSI
        bin_width = (rmax - rmin) / self.bins
        # build hist counts
        r_counts = [0] * self.bins
        c_counts = [0] * self.bins
        def bin_index(val: float) -> int:
            idx = int((val - rmin) / bin_width)
            if idx >= self.bins:
                idx = self.bins - 1
            if idx < 0:
                idx = 0
            return idx
        for v in ref:
            r_counts[bin_index(v)] += 1
        for v in cur:
            # clamp to range; values outside reference range extend to nearest bin
            if v < rmin:
                idx = 0
            elif v > rmax:
                idx = self.bins - 1
            else:
                idx = bin_index(v)
            c_counts[idx] += 1
        r_total = float(sum(r_counts)) or 1.0
        c_total = float(sum(c_counts)) or 1.0
        psi = 0.0
        for rc, cc in zip(r_counts, c_counts):
            p = rc / r_total
            q = cc / c_total
            p = max(p, _EPS)
            q = max(q, _EPS)
            psi += (p - q) * math.log(p / q)
        return psi

# Singleton (lightweight)
_drift_monitor: DriftMonitor | None = None

def drift_monitor() -> DriftMonitor:
    global _drift_monitor
    if _drift_monitor is None:
        _drift_monitor = DriftMonitor()
    return _drift_monitor

__all__ = ["DriftMonitor", "drift_monitor"]
