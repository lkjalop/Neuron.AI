"""Baseline statistical detector.

Per-tenant rolling window mean/std dev anomaly detection for selected numeric features.
Features considered: all numeric in event.features (float/int) by default.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List
import math

from core.shared_anomalies import anomaly_buffer

from core.event import Event
from core import metrics
from config import runtime_params
from .interface import DetectionResult, IDetector, registry
from core.sequence.buffer import buffers as vector_buffers
from core.features.registry import feature_order, to_vector


@dataclass
class FeatureStats:
    window: Deque[float]
    mean: float = 0.0
    m2: float = 0.0  # sum of squares of differences for variance

    def update(self, value: float, max_len: int):
        # Welford update
        self.window.append(value)
        if len(self.window) > max_len:
            # Recompute after dropping (simpler, small window sizes expected)
            self.window.popleft()
            self._recompute()
        else:
            n = len(self.window)
            delta = value - self.mean
            self.mean += delta / n
            delta2 = value - self.mean
            self.m2 += delta * delta2

    def _recompute(self):
        n = len(self.window)
        if n == 0:
            self.mean = 0.0
            self.m2 = 0.0
            return
        self.mean = sum(self.window) / n
        self.m2 = sum((x - self.mean) ** 2 for x in self.window)

    @property
    def variance(self) -> float:
        n = len(self.window)
        if n < 2:
            return 0.0
        return self.m2 / (n - 1)

    @property
    def std(self) -> float:
        return math.sqrt(self.variance)


class BaselineDetector(IDetector):
    name = "baseline"

    def __init__(self, window: int = 50, stddev_threshold: float = 3.0, warmup_min: int = 10, use_mad: bool = True, mad_factor: float = 3.5):
        self.window = window
        self.stddev_threshold = stddev_threshold
        self.warmup_min = warmup_min
        self.use_mad = use_mad
        self.mad_factor = mad_factor
        self.state: Dict[str, Dict[str, FeatureStats]] = {}
        # metrics counters local (optional future): warmup skips, mad_used counts
        self._warmup_skips = 0
        self._mad_used = 0
        self._jitter_applied = False
        self._skipped_events_due_to_jitter = 0

    def _mad_threshold(self, values: Deque[float]) -> float:
        if len(values) < self.warmup_min:
            return float('inf')  # skip anomaly decision
        median = self._median(values)
        deviations = [abs(x - median) for x in values]
        mad = self._median(deviations) or 0.0
        if mad == 0:
            return float('inf')  # no variability yet
        # Approximate z-like scaling: 1.4826 * MAD ~ std for normal distribution
        return self.mad_factor * 1.4826 * mad

    @staticmethod
    def _median(seq: Deque[float]) -> float:
        s = sorted(seq)
        n = len(s)
        if n == 0:
            return 0.0
        mid = n // 2
        if n % 2 == 1:
            return s[mid]
        return (s[mid - 1] + s[mid]) / 2

    def process(self, event: Event) -> List[DetectionResult]:
        tenant_state = self.state.setdefault(event.tenant_id, {})
        anomalies: List[DetectionResult] = []
        # Apply optional warm-up jitter event skipping
        try:
            jitter_events = int(runtime_params.get_param("baseline.warmup_jitter_events") or 0)
        except Exception:
            jitter_events = 0
        if jitter_events > 0 and self._skipped_events_due_to_jitter < jitter_events:
            self._skipped_events_due_to_jitter += 1
            metrics.DETECTOR_WARMUP_SKIPS.labels(tenant=event.tenant_id, detector=self.name).inc()
            return []
        # Potential dynamic parameter lookup (cached values could be optimized if hot path)
        dynamic_threshold = runtime_params.get_param("baseline.stddev_threshold") or self.stddev_threshold
        use_hybrid = bool(runtime_params.get_param("baseline.use_hybrid"))
        for feat, val in event.features.items():
            if not isinstance(val, (int, float)):
                continue
            stats = tenant_state.get(feat)
            if stats is None:
                stats = FeatureStats(window=deque(maxlen=self.window))
                tenant_state[feat] = stats
            # Warm-up gating
            history_len = len(stats.window)
            decision_reason = "warmup" if history_len < self.warmup_min else "std"
            mean = stats.mean
            std = stats.std
            is_anom = False
            z = None
            adaptive_used = False
            if history_len >= self.warmup_min:
                if std > 0:
                    z = (val - mean) / std
                    if use_hybrid:
                        # Evaluate both z and MAD style threshold (if enabled) and choose first firing reason
                        z_flag = abs(z) >= dynamic_threshold
                        mad_flag = False
                        if self.use_mad:
                            adaptive_used = True
                            threshold = self._mad_threshold(stats.window)
                            deviation = abs(val - self._median(stats.window))
                            mad_flag = deviation >= threshold
                        if z_flag:
                            is_anom = True
                            decision_reason = "hybrid_z"
                        elif mad_flag:
                            is_anom = True
                            decision_reason = "hybrid_mad"
                    else:
                        if abs(z) >= dynamic_threshold:
                            is_anom = True
                else:
                    # zero variance so far; fallback strategies
                    if self.use_mad:
                        adaptive_used = True
                        threshold = self._mad_threshold(stats.window)
                        deviation = abs(val - self._median(stats.window))
                        if deviation >= threshold:
                            is_anom = True
                            decision_reason = "mad" if not use_hybrid else "hybrid_mad"
                    # Additional absolute deviation heuristic: if all values equal and new value differs significantly
                    if not is_anom and stats.window and abs(val - mean) >= dynamic_threshold:
                        is_anom = True
                        decision_reason = "abs_delta"
            else:
                self._warmup_skips += 1
                metrics.DETECTOR_WARMUP_SKIPS.labels(tenant=event.tenant_id, detector=self.name).inc()
            stats.update(float(val), self.window)
            if adaptive_used:
                self._mad_used += 1
                metrics.DETECTOR_MAD_FALLBACK.labels(tenant=event.tenant_id, detector=self.name).inc()
            if is_anom:
                anomalies.append(DetectionResult({
                    "feature": feat,
                    "value": float(val),
                    "mean": mean,
                    "std": std,
                    "z": z,
                    "detector": self.name,
                    "tenant": event.tenant_id,
                    "event_id": event.event_id,
                    "trace_id": event.trace_id,
                    "reason": decision_reason,
                }))
        if anomalies:
            metrics.ANOMALIES_TOTAL.labels(tenant=event.tenant_id, detector=self.name).inc()
            # Push anomalies to global buffer per tenant
            for a in anomalies:
                enriched = {
                    "event_id": a["event_id"],
                    "tenant_id": a["tenant"],
                    "detector": a["detector"],
                    "trace_id": a.get("trace_id"),
                    "feature": a.get("feature"),
                    "reason": a.get("reason"),
                    "value": a.get("value"),
                }
                # Attach case context if available (best-effort; lazy import to avoid cycle)
                try:
                    from core.main import _CASE_ID_INDEX, _CASES  # type: ignore
                    anomaly_id = a.get("event_id") or a.get("id")
                    if anomaly_id and anomaly_id in _CASE_ID_INDEX:
                        cid = _CASE_ID_INDEX[anomaly_id]
                        case = _CASES.get(cid)
                        if case:
                            enriched["case_id"] = cid
                            lc = case.get("last_confidence")
                            if lc is not None:
                                enriched["case_confidence"] = lc
                except Exception:
                    pass
                anomaly_buffer.add(event.tenant_id, enriched)
        # Optional temporal residual injection: small synthetic anomaly when normalized window variance spikes
        try:
            if bool(runtime_params.get_param("temporal.residual.enable")):
                order = feature_order()
                vec = to_vector({k: v for k, v in event.features.items() if isinstance(v, (int, float))})
                win = int(runtime_params.get_param("snn.encoding_window") or 20)
                mgr = vector_buffers(window=win, feature_order=order)
                vbuf = mgr.get(event.tenant_id)
                # add vector (duplicate add relative to pipeline ok; cheap) then compute simple variance change
                try:
                    vbuf.add_vector(vec)
                except Exception:
                    pass
                if vbuf.ready():
                    window_view = vbuf.window_view()
                    # compute per-dim variance of normalized values (0..1)
                    if window_view:
                        dims = len(window_view[0])
                        var_sum = 0.0
                        for j in range(dims):
                            col = [row[j] for row in window_view]
                            m = sum(col) / len(col)
                            var = sum((x - m) ** 2 for x in col) / max(1, len(col) - 1)
                            var_sum += var
                        mean_var = var_sum / max(1, dims)
                        # simple heuristic: if mean variance above 0.15 treat as micro anomaly
                        if mean_var > 0.15:
                            anomalies.append(DetectionResult({
                                "feature": "_temporal_residual",
                                "value": mean_var,
                                "detector": self.name,
                                "tenant": event.tenant_id,
                                "event_id": event.event_id,
                                "trace_id": event.trace_id,
                                "reason": "temporal_residual_var_spike",
                            }))
                            metrics.ANOMALIES_TOTAL.labels(tenant=event.tenant_id, detector=self.name).inc()
        except Exception:
            pass
        return anomalies


# Register instance helper (optional usage by pipeline)
def register_default(window: int = 50, stddev_threshold: float = 3.0) -> BaselineDetector:
    det = BaselineDetector(window=window, stddev_threshold=stddev_threshold)
    registry.register(det)
    return det


__all__ = ["BaselineDetector", "register_default"]
