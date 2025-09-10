"""Detector Orchestrator

Central pipeline to execute enabled detectors in cost-prioritized order,
aggregate results, and emit metrics & precision proxy tagging.

Design Goals:
 - Pluggable detectors with consistent interface.
 - Per-detector latency + anomaly emission counting.
 - Precision proxy: mark anomalies occurring in configured noise windows.
 - Minimal dependencies beyond existing metrics module.

Detectors implement:
class Detector:
    name: str
    cost_hint: float  # relative ordering (lower first)
    def evaluate(self, event: Event) -> list[Anomaly]: ...
    def flush(self): optional hook

Anomaly schema (lightweight) kept local to avoid tight coupling.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Protocol, List, Dict, Iterable, Optional
import time, os, json, pathlib, collections

from core.event import Event
from core import metrics
from .flush import flush_all
try:
    # Optional baseline import (may be excluded for experimentation)
    from .baseline_detector import RollingStatsDetector  # type: ignore
except Exception:  # pragma: no cover - baseline optional
    RollingStatsDetector = None  # type: ignore

class _FallbackBaseline:
    """Very small fallback detector for tests when primary baseline disabled.

    Maintains a short window and flags values greater than mean+3*std (or +10 absolute) after 5 samples.
    """
    name = "baseline_stats"
    cost_hint = 0.05
    def __init__(self):
        self.values: list[float] = []
    def evaluate(self, event: Event):
        if event.severity is None:
            return []
        v = float(event.severity)
        self.values.append(v)
        if len(self.values) > 30:
            self.values.pop(0)
        if len(self.values) < 5:
            return []
        mean = sum(self.values)/len(self.values)
        var = sum((x-mean)**2 for x in self.values)/len(self.values)
        std = var ** 0.5
        threshold = mean + 3*std if std > 0 else mean + 10
        if v >= threshold:
            return [Anomaly(event_id=event.event_id, detector=self.name, score=(v-mean)/(std or 1.0), reason=f"fallback z threshold", ts=time.time(), tenant_id=event.tenant_id)]
        return []
    def flush(self):
        return None


@dataclass
class Anomaly:
    event_id: str
    detector: str
    score: float
    reason: str
    ts: float
    tenant_id: Optional[str]
    meta: Dict[str, float | int | str | bool] | None = None

    def to_dict(self) -> Dict:
        return asdict(self)


class Detector(Protocol):
    name: str
    cost_hint: float

    def evaluate(self, event: Event) -> List[Anomaly]:
        ...

    def flush(self) -> None:  # noqa: D401 - Simple protocol hook
        """Optional flush to finalize state (e.g., batch models)."""
        return None


class DetectorRegistry:
    def __init__(self):
        self._detectors: List[Detector] = []

    def register(self, detector: Detector):
        self._detectors.append(detector)
        # maintain ordering by cost
        self._detectors.sort(key=lambda d: getattr(d, 'cost_hint', 1.0))

    def enabled(self) -> Iterable[Detector]:
        return list(self._detectors)


class Orchestrator:
    def __init__(self, registry: DetectorRegistry, *, precision_proxy_fn=None, anomaly_sink_dir: Optional[pathlib.Path] = None, fusion_strategy=None):
        self.registry = registry
        self.precision_proxy_fn = precision_proxy_fn  # fn(event) -> bool (is noise window)
        self.anomaly_sink_dir = anomaly_sink_dir or pathlib.Path('artifacts/dataset')
        self.anomaly_sink_dir.mkdir(parents=True, exist_ok=True)
        self._anomaly_log_path = self.anomaly_sink_dir / 'anomaly_log.jsonl'
        # Tracking for precision proxy rate: false positives per (tenant, detector) and noise window counts
        self._pp_false: Dict[tuple[str, str], int] = collections.defaultdict(int)
        self._pp_windows: Dict[str, int] = collections.defaultdict(int)
        self._fusion = fusion_strategy if os.getenv('ENABLE_FUSION', 'false').lower() == 'true' else None

    def process_event(self, event: Event) -> List[Anomaly]:
        tenant = event.tenant_id or "global"
        out: List[Anomaly] = []
        detectors_fired: set[str] = set()
        for det in self.registry.enabled():
            start = time.perf_counter()
            try:
                anomalies = det.evaluate(event) or []
            except Exception as exc:  # robust isolation
                metrics.INGEST_ERRORS_TOTAL.labels(error_type=f"detector_{det.name}_error").inc()
                continue
            elapsed = time.perf_counter() - start
            metrics.DETECTOR_LATENCY.labels(tenant=tenant, detector=det.name).observe(elapsed)
            for a in anomalies:
                out.append(a)
                metrics.ANOMALIES_TOTAL.labels(tenant=tenant, detector=det.name).inc()
                if self.precision_proxy_fn and self.precision_proxy_fn(event):
                    metrics.PRECISION_PROXY_FALSE_POSITIVE.labels(tenant=tenant, detector=det.name).inc()
                    self._pp_false[(tenant, det.name)] += 1
                detectors_fired.add(det.name)
            # update proxy windows count only once per event if noise event
        if self.precision_proxy_fn and self.precision_proxy_fn(event):
            metrics.PRECISION_PROXY_WINDOWS.labels(tenant=tenant).inc()
            self._pp_windows[tenant] += 1
            # Update precision proxy rate for each detector with at least one recorded false positive
            windows = self._pp_windows[tenant]
            if windows > 0:
                for (t, det_name), count in list(self._pp_false.items()):
                    if t == tenant:
                        rate = count / windows
                        metrics.PRECISION_PROXY_RATE.labels(tenant=tenant, detector=det_name).set(rate)
        # Write append anomalies
        if out:
            with self._anomaly_log_path.open('a', encoding='utf-8') as f:
                for a in out:
                    f.write(json.dumps(a.to_dict()) + "\n")
            # Unique contribution metrics
            metrics.UNION_EVENTS_TOTAL.labels(tenant=tenant).inc()
            if len(detectors_fired) == 1:
                # Exactly one detector
                only = next(iter(detectors_fired))
                metrics.DETECTOR_UNIQUE_EVENTS_TOTAL.labels(tenant=tenant, detector=only).inc()
            else:
                for dname in detectors_fired:
                    metrics.DETECTOR_OVERLAP_EVENTS_TOTAL.labels(tenant=tenant, detector=dname).inc()
            # Update ratios for detectors involved
            # We need total union so far -> sum of UNION_EVENTS_TOTAL counter is not directly accessible; skip expensive registry scrape.
            # Approximation: maintain per-process dictionary (could extend state). For simplicity, compute ratio from counters by caching union count.
            # Simple internal cache
            if not hasattr(self, '_union_cache'):
                self._union_cache = {tenant: 0}
            self._union_cache[tenant] = self._union_cache.get(tenant, 0) + 1
            union = self._union_cache[tenant]
            for dname in detectors_fired:
                # unique count pulled from _pp_false? we have counters not accessible; we won't query registry, so maintain internal unique map too.
                if not hasattr(self, '_unique_cache'):
                    self._unique_cache = {}
                key = (tenant, dname)
                # increment unique cache if only detector
                if len(detectors_fired) == 1:
                    self._unique_cache[key] = self._unique_cache.get(key, 0) + 1
                # compute ratio
                unique_val = self._unique_cache.get(key, 0)
                ratio = unique_val / union if union else 0.0
                metrics.DETECTOR_UNIQUE_RATIO.labels(tenant=tenant, detector=dname).set(ratio)
        # --- Fusion step (optional) ---
        if self._fusion and out:
            try:
                f_start = time.perf_counter()
                fused_list = self._fusion.fuse(out)  # expect original anomalies + fused appended
                f_elapsed = time.perf_counter() - f_start
                if fused_list and len(fused_list) > len(out):
                    # Identify new anomalies (by detector name == fusion name)
                    added = fused_list[len(out):]
                    for fa in added:
                        metrics.ANOMALIES_TOTAL.labels(tenant=tenant, detector=fa.detector).inc()
                        # Track fusion count
                        if hasattr(metrics, 'FUSION_ANOMALIES_TOTAL'):
                            metrics.FUSION_ANOMALIES_TOTAL.labels(tenant=tenant, strategy=self._fusion.name).inc()
                        if hasattr(metrics, 'FUSION_SCORE'):
                            metrics.FUSION_SCORE.labels(tenant=tenant, strategy=self._fusion.name).observe(fa.score)
                        # Contributor weights gauge
                        if fa.meta and 'contributors' in fa.meta and hasattr(metrics, 'FUSION_CONTRIBUTOR_WEIGHT'):
                            for det_name, contrib in fa.meta['contributors'].items():
                                metrics.FUSION_CONTRIBUTOR_WEIGHT.labels(tenant=tenant, detector=det_name).set(contrib)
                    if hasattr(metrics, 'DETECTOR_LATENCY'):
                        metrics.DETECTOR_LATENCY.labels(tenant=tenant, detector=self._fusion.name).observe(f_elapsed)
                    out = fused_list
            except Exception:
                pass
        return out

    def flush(self):
        flush_all(self.registry.enabled())


# --- Baseline detector wrapper (placeholder) ---
def default_precision_proxy(event: Event) -> bool:
    # Placeholder heuristic: treat events with severity < 0.5 as noise window candidates
    if event.severity is None:
        return False
    return event.severity < 0.5


def build_default_orchestrator(include_baseline: bool = True) -> Orchestrator:
    reg = DetectorRegistry()
    if include_baseline:
        if RollingStatsDetector is not None:
            try:
                reg.register(RollingStatsDetector())
            except Exception:
                reg.register(_FallbackBaseline())
        else:
            reg.register(_FallbackBaseline())
    # Optional detectors (best-effort registration)
    # Isolation Forest
    try:  # local import to avoid heavy deps when flag not set
        from .isolation_forest_detector import IsolationForestDetector  # type: ignore
        try:
            reg.register(IsolationForestDetector())
        except Exception:
            pass
    except Exception:
        pass
    # SNN
    try:
        from .snn_detector import SNNDetector  # type: ignore
        try:
            reg.register(SNNDetector())
        except Exception:
            pass
    except Exception:
        pass
    # Temporal
    try:
        from .temporal_detector import TemporalDetector  # type: ignore
        try:
            reg.register(TemporalDetector())
        except Exception:
            pass
    except Exception:
        pass
    fusion_strategy = None
    if os.getenv('ENABLE_FUSION', 'false').lower() == 'true':
        strategy_name = os.getenv('FUSION_STRATEGY', 'weighted_temporal').lower()
        try:
            if strategy_name == 'weighted_temporal':
                from fusion.weighted_temporal import WeightedTemporalFusion  # type: ignore
                fusion_strategy = WeightedTemporalFusion()
            else:
                # Unknown strategy placeholder; could raise later
                fusion_strategy = None
        except Exception:
            fusion_strategy = None
        # Set fusion active gauge if available
        if fusion_strategy and hasattr(metrics, 'FUSION_ACTIVE'):
            try:
                metrics.FUSION_ACTIVE.labels(strategy=fusion_strategy.name).set(1)
            except Exception:
                pass
    else:
        if hasattr(metrics, 'FUSION_ACTIVE'):
            try:
                metrics.FUSION_ACTIVE.labels(strategy='none').set(0)
            except Exception:
                pass
    return Orchestrator(registry=reg, precision_proxy_fn=default_precision_proxy, fusion_strategy=fusion_strategy)


__all__ = [
    "Anomaly",
    "Detector",
    "DetectorRegistry",
    "Orchestrator",
    "RollingStatsDetector",
    "build_default_orchestrator",
]
