from __future__ import annotations
"""Automation watchers for SLA breach detection and anomaly (factor volatility) monitoring.

Lightweight stubs:
 - SLABreachWatcher: scans findings metadata / risk artifacts (placeholder function hooks) and emits SLA breach metrics.
 - FactorVolatilityMonitor: tracks exponential weighted variance of factor contribution shares to detect drift spikes.

These are framework stubs; integration points (data access) should be adapted once full finding store exists.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Optional
import time
import math
from pathlib import Path
import json

from core.metrics import (
    VULN_SLA_BREACH_TOTAL,
    VULN_SLA_BREACH_ACTIVE,
    VULN_AUTOMATION_EVENTS_TOTAL,
    VULN_FACTOR_VOLATILITY,
    VULN_ANOMALY_DETECTIONS_TOTAL,
    VULN_ALERT_DISPATCH_TOTAL,
    VULN_SLA_COUNTDOWN_DAYS,
    FACTOR_MAHALANOBIS_DISTANCE,
    FACTOR_DRIFT_ANOMALIES_TOTAL,
)

SEVERITY_SLA_DAYS = {
    "CRITICAL": 7,
    "HIGH": 30,
    "MEDIUM": 90,
    "LOW": 180,
}

@dataclass
class SLABreachWatcher:
    fetch_findings: Callable[[], List[Dict]]
    now_fn: Callable[[], float] = time.time
    artifacts_dir: Path = Path("artifacts")

    def check(self) -> None:
        findings = self.fetch_findings() or []
        active_counts = {s: 0 for s in SEVERITY_SLA_DAYS}
        now = self.now_fn()
        for f in findings:
            sev = f.get("severity_label") or f.get("severity") or "LOW"
            opened_ts = f.get("opened_ts")  # expected epoch seconds
            fixed_ts = f.get("fixed_ts")
            if not opened_ts or fixed_ts:
                continue
            deadline_days = SEVERITY_SLA_DAYS.get(sev, 180)
            age_days = (now - opened_ts) / 86400.0
            remaining = deadline_days - age_days
            if remaining <= 0:
                # breach event
                VULN_SLA_BREACH_TOTAL.labels(severity=sev).inc()
                VULN_AUTOMATION_EVENTS_TOTAL.labels(type="sla_breach").inc()
                active_counts[sev] += 1
            else:
                # track minimum countdown gauge per severity
                current = VULN_SLA_COUNTDOWN_DAYS.labels(severity=sev)
                # naive set (Gauge API doesn't expose get; rely on last set overshadow)
                current.set(min(max(remaining, 0), deadline_days))
        for sev, c in active_counts.items():
            VULN_SLA_BREACH_ACTIVE.labels(severity=sev).set(c)
        # persist snapshot (optional)
        snap_path = self.artifacts_dir / "sla_breach_snapshot.json"
        snap = {"ts": now, "active": active_counts}
        try:
            snap_path.write_text(json.dumps(snap, indent=2))
        except Exception:
            pass

@dataclass
class FactorVolatilityMonitor:
    fetch_factor_shares: Callable[[], Dict[str, float]]
    alpha: float = 0.2  # EW smoothing
    threshold: float = 0.15  # volatility trigger
    state: Dict[str, Dict[str, float]] = field(default_factory=dict)
    audit_path: Path = Path("audit/VOLATILITY_ANOMALIES.jsonl")

    def step(self) -> None:
        shares = self.fetch_factor_shares() or {}
        for factor, value in shares.items():
            st = self.state.setdefault(factor, {"mean": value, "m2": 0.0})
            # EW incremental variance (using Welford-like but simplified)
            prev_mean = st["mean"]
            new_mean = (1 - self.alpha) * prev_mean + self.alpha * value
            # approximate EW variance update
            diff = value - prev_mean
            new_var = (1 - self.alpha) * st["m2"] + self.alpha * diff * diff
            st["mean"] = new_mean
            st["m2"] = new_var
            volatility = math.sqrt(new_var)
            VULN_FACTOR_VOLATILITY.labels(factor=factor).set(volatility)
            if volatility >= self.threshold:
                VULN_ANOMALY_DETECTIONS_TOTAL.labels(detector="factor_volatility", factor=factor).inc()
                VULN_AUTOMATION_EVENTS_TOTAL.labels(type="anomaly").inc()
                # Persist anomaly record JSONL
                try:
                    self.audit_path.parent.mkdir(parents=True, exist_ok=True)
                    rec = {
                        "ts": time.time(),
                        "factor": factor,
                        "volatility": volatility,
                        "threshold": self.threshold,
                        "mean": st.get("mean"),
                    }
                    with self.audit_path.open('a', encoding='utf-8') as fh:
                        fh.write(json.dumps(rec) + '\n')
                except Exception:
                    pass


@dataclass
class FactorDriftDetector:
    """Multivariate drift placeholder using simplified Mahalanobis distance.

    Maintains EW mean vector and EW covariance diagonal (independent approximation) for factor share vector.
    This is a placeholder (not full covariance inversion) to keep computation trivial; it still provides
    a distance-like scalar useful for thresholding. Future enhancement: maintain full covariance matrix
    and compute (x-mean)^T Sigma^{-1} (x-mean).
    """
    fetch_factor_shares: Callable[[], Dict[str, float]]
    alpha: float = 0.1
    threshold: float = 2.5  # heuristic distance trigger
    mean: Dict[str, float] = field(default_factory=dict)
    var: Dict[str, float] = field(default_factory=dict)  # EW variance per factor

    def step(self) -> None:
        shares = self.fetch_factor_shares() or {}
        if not shares:
            return
        # Update EW mean/variance
        for f, v in shares.items():
            m_prev = self.mean.get(f, v)
            m_new = (1 - self.alpha) * m_prev + self.alpha * v
            # variance update (EW)
            diff = v - m_prev
            var_prev = self.var.get(f, 0.0)
            var_new = (1 - self.alpha) * var_prev + self.alpha * diff * diff
            self.mean[f] = m_new
            # ensure non-zero floor to avoid div-by-zero
            self.var[f] = max(var_new, 1e-6)
        # Compute pseudo Mahalanobis distance (diagonal approximation)
        dist_sq = 0.0
        for f, v in shares.items():
            m = self.mean.get(f, v)
            var = self.var.get(f, 1e-6)
            z = (v - m) / (var ** 0.5)
            dist_sq += z * z
        try:
            FACTOR_MAHALANOBIS_DISTANCE.set(dist_sq ** 0.5)
        except Exception:
            pass
        if dist_sq ** 0.5 >= self.threshold:
            try:
                FACTOR_DRIFT_ANOMALIES_TOTAL.labels(detector="mahalanobis").inc()
                VULN_AUTOMATION_EVENTS_TOTAL.labels(type="anomaly").inc()
            except Exception:
                pass

# Simple alert dispatcher placeholder
class AlertDispatcher:
    def __init__(self, sink: Optional[Callable[[Dict], None]] = None):
        self.sink = sink

    def dispatch(self, payload: Dict) -> None:
        try:
            if self.sink:
                self.sink(payload)
            VULN_ALERT_DISPATCH_TOTAL.labels(outcome="success").inc()
            VULN_AUTOMATION_EVENTS_TOTAL.labels(type="alert_dispatch").inc()
        except Exception:
            VULN_ALERT_DISPATCH_TOTAL.labels(outcome="error").inc()

__all__ = [
    "SLABreachWatcher",
    "FactorVolatilityMonitor",
    "AlertDispatcher",
]
