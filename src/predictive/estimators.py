from __future__ import annotations
"""Predictive scaffold for time-to-remediation, exploit likelihood timeline, and exposure clustering.

These are lightweight heuristics / placeholders to be replaced with richer models later.
"""
from dataclasses import dataclass
from typing import List, Dict, Callable, Optional
from pathlib import Path
import json
import math
import time

from core.metrics import (
    VULN_TTR_ESTIMATE_DAYS,
    VULN_TTR_CONFIDENCE,
    VULN_EXPLOIT_LIKELIHOOD,
    VULN_EXPLOIT_TREND_SLOPE,
    VULN_EXPOSURE_CLUSTER_COUNT,
    VULN_EXPOSURE_CLUSTER_RISK,
    VULN_PREDICTIVE_MODEL_UPDATE_TOTAL,
    VULN_AUTOMATION_EVENTS_TOTAL,
)
try:
    from config import runtime_params  # type: ignore
except Exception:  # pragma: no cover
    runtime_params = None  # type: ignore

@dataclass
class TimeToRemediateEstimator:
    fetch_burndown_series: Callable[[], List[Dict]]  # list of {ts: epoch_seconds, open: int}
    artifacts_dir: Path = Path("artifacts")

    def compute(self) -> None:
        series = self.fetch_burndown_series() or []
        if len(series) < 3:
            return
        # Optional severity weighting: expects runtime param predictive.ttr.severity_weights
        weights_map = None
        try:
            if runtime_params:
                wm = runtime_params.get_param("predictive.ttr.severity_weights")
                if isinstance(wm, dict):
                    # normalize to floats
                    weights_map = {k.upper(): float(v) for k,v in wm.items() if isinstance(v, (int,float,str))}
        except Exception:
            weights_map = None
        # Accept series points optionally containing severity_counts {CRITICAL: x, HIGH: y, ...}
        xs = [(pt["ts"] // 86400) for pt in series]
        raw_open = [pt.get("open", 0) for pt in series]
        if weights_map:
            weighted = []
            for pt in series:
                sev_counts = pt.get("severity_counts") or {}
                total = 0.0
                # If we have per-severity counts apply weights, else fallback to open
                if isinstance(sev_counts, dict) and sev_counts:
                    for sev, cnt in sev_counts.items():
                        try:
                            w = float(weights_map.get(str(sev).upper(), 1.0))
                        except Exception:
                            w = 1.0
                        try:
                            total += w * float(cnt)
                        except Exception:
                            continue
                else:
                    total = pt.get("open", 0)
                weighted.append(total)
            ys = weighted
        else:
            ys = raw_open
        n = len(xs)
        mean_x = sum(xs)/n
        mean_y = sum(ys)/n
        num = sum((x-mean_x)*(y-mean_y) for x,y in zip(xs,ys))
        den = sum((x-mean_x)**2 for x in xs) or 1.0
        slope = num/den  # findings per day (negative desirable)
        if slope >= 0:
            # no downward trend
            VULN_TTR_CONFIDENCE.set(0.1)
            return
        last_x = xs[-1]
        last_y = ys[-1]
        # days to zero: y + slope*(d) = 0 => d = -y/slope
        eta_days = -last_y / slope
        confidence = min(1.0, max(0.0, abs(slope) / (last_y + 1)))
        VULN_TTR_ESTIMATE_DAYS.set(eta_days)
        VULN_TTR_CONFIDENCE.set(confidence)
        payload = {
            "eta_days": eta_days,
            "slope": slope,
            "confidence": confidence,
            "last_open_weighted": last_y,
            "last_open_raw": raw_open[-1] if raw_open else None,
            "weights_applied": bool(weights_map),
            "severity_weights": weights_map,
        }
        out = self.artifacts_dir / "predictive_time_to_remediate.json"
        try:
            out.write_text(json.dumps(payload, indent=2))
        except Exception:
            pass
        VULN_PREDICTIVE_MODEL_UPDATE_TOTAL.labels(model="ttr").inc()
        VULN_AUTOMATION_EVENTS_TOTAL.labels(type="predictive_update").inc()

@dataclass
class ExploitLikelihoodModel:
    fetch_recent_vulns: Callable[[], List[Dict]]  # list of {cve, epss, exploit_available, kev_listed}
    artifacts_dir: Path = Path("artifacts")
    decay_alpha: float = 0.3
    state: Dict[str, float] = None

    def tick(self) -> None:
        vulns = self.fetch_recent_vulns() or []
        if self.state is None:
            self.state = {}
        agg_slope_window = []
        for v in vulns:
            cve = v.get("cve") or v.get("cve_id")
            base = (v.get("epss") or 0.0)
            if v.get("exploit_available"):
                base = min(1.0, base + 0.2)
            if v.get("kev_listed"):
                base = min(1.0, base + 0.2)
            prev = self.state.get(cve, base)
            updated = (1 - self.decay_alpha) * prev + self.decay_alpha * base
            self.state[cve] = updated
            agg_slope_window.append(updated)
        # Top-N gating
        top_n = None
        try:
            if runtime_params:
                tv = runtime_params.get_param("predictive.exploit.top_n")
                if tv is not None:
                    top_n = int(tv)
        except Exception:
            top_n = None
        items_sorted = sorted(self.state.items(), key=lambda kv: kv[1], reverse=True)
        if top_n is not None and top_n > 0:
            items_sorted = items_sorted[:top_n]
        for cve_val, score in items_sorted:
            try:
                VULN_EXPLOIT_LIKELIHOOD.labels(cve=cve_val).set(score)
            except Exception:
                pass
        # naive trend slope across CVEs (treat index as ordered proxy)
        if len(agg_slope_window) >= 3:
            xs = list(range(len(agg_slope_window)))
            ys = agg_slope_window
            n = len(xs)
            mean_x = sum(xs)/n
            mean_y = sum(ys)/n
            num = sum((x-mean_x)*(y-mean_y) for x,y in zip(xs,ys))
            den = sum((x-mean_x)**2 for x in xs) or 1.0
            slope = num/den
            VULN_EXPLOIT_TREND_SLOPE.set(slope)
        out = self.artifacts_dir / "exploit_likelihood_timeline.json"
        try:
            out.write_text(json.dumps({"ts": time.time(), "likelihoods": self.state}, indent=2))
        except Exception:
            pass
        VULN_PREDICTIVE_MODEL_UPDATE_TOTAL.labels(model="exploit").inc()
        VULN_AUTOMATION_EVENTS_TOTAL.labels(type="predictive_update").inc()

@dataclass
class ExposureClustering:
    fetch_open_findings: Callable[[], List[Dict]]
    artifacts_dir: Path = Path("artifacts")
    max_clusters: int = 5

    def recompute(self) -> None:
        findings = self.fetch_open_findings() or []
        if not findings:
            return
        # Placeholder: group by severity_label only
        clusters: Dict[str, List[Dict]] = {}
        for f in findings:
            key = f.get("severity_label", "LOW")
            clusters.setdefault(key, []).append(f)
        # Compute risk aggregate per cluster
        cluster_scores = {}
        for cid, items in clusters.items():
            total = 0.0
            for it in items:
                r = it.get("risk", {}).get("normalized_score") or it.get("risk_score") or 0.0
                total += r
            cluster_scores[cid] = total
            VULN_EXPOSURE_CLUSTER_RISK.labels(cluster_id=cid).set(total)
        VULN_EXPOSURE_CLUSTER_COUNT.set(len(cluster_scores))
        out = self.artifacts_dir / "exposure_clusters.json"
        try:
            out.write_text(json.dumps({"ts": time.time(), "clusters": cluster_scores}, indent=2))
        except Exception:
            pass
        VULN_PREDICTIVE_MODEL_UPDATE_TOTAL.labels(model="exposure").inc()
        VULN_AUTOMATION_EVENTS_TOTAL.labels(type="predictive_update").inc()

__all__ = [
    "TimeToRemediateEstimator",
    "ExploitLikelihoodModel",
    "ExposureClustering",
]
