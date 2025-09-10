"""Reporting template engine (HTML) using Jinja2.

Current templates:
 - executive_summary.html
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List, Tuple
import time, json, re, math

from jinja2 import Environment, FileSystemLoader, select_autoescape  # type: ignore
from storage import postgres

TEMPLATE_DIR = Path(__file__).parent / 'templates'

env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(['html', 'xml'])
)


async def load_dashboard_snapshot() -> Dict[str, Any]:
    rows = await postgres.fetch("SELECT data FROM dashboard_cache WHERE snapshot_type='main'")
    if not rows:
        return {}
    data = rows[0][0]
    if isinstance(data, str):
        import json as _json
        try:
            return _json.loads(data)
        except Exception:
            return {}
    return data or {}


def _sparkline(values: List[float], width: int = 120, height: int = 30, stroke: str = "#2c7") -> str:
    if not values:
        return f"<svg width='{width}' height='{height}'></svg>"
    mn = min(values)
    mx = max(values)
    span = (mx - mn) or 1.0
    pts = []
    for i, v in enumerate(values):
        x = (i / max(1, len(values)-1)) * (width-4) + 2
        y = height - 2 - ((v - mn) / span) * (height - 4)
        pts.append(f"{x:.2f},{y:.2f}")
    poly = " ".join(pts)
    return f"<svg width='{width}' height='{height}' viewBox='0 0 {width} {height}'><polyline fill='none' stroke='{stroke}' stroke-width='1.5' points='{poly}'/></svg>"


def _extract_temporal_weight_history(max_items: int = 100) -> List[Tuple[float,float]]:
    """Parse recent temporal weight adjustments from audit markdown (best-effort)."""
    path = Path('audit/AUDIT_LOG.md')
    if not path.exists():
        return []
    pat = re.compile(r"PARAM_CHANGE key=detection\.temporal\.weight old=([0-9.]+|None) new=([0-9.]+)")
    hist: List[Tuple[float,float]] = []
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
        for line in reversed(lines):
            m = pat.search(line)
            if m:
                try:
                    old_v = float(m.group(1)) if m.group(1) != 'None' else math.nan
                    new_v = float(m.group(2))
                    hist.append((old_v, new_v))
                except Exception:
                    continue
                if len(hist) >= max_items:
                    break
    except Exception:
        return []
    return list(reversed(hist))


async def render_executive_summary() -> str:
    snap = await load_dashboard_snapshot()
    comp_hist = snap.get('governance', {}).get('composite_history') or []
    composite_spark = _sparkline([float(v) for v in comp_hist][-60:])  # last 60 points
    temporal_hist_pairs = _extract_temporal_weight_history()
    temporal_series = [nv for _ov, nv in temporal_hist_pairs]
    temporal_spark = _sparkline(temporal_series[-60:], stroke="#c72") if temporal_series else ""
    # Exposure trend sparkline (daily risk totals)
    exposure_daily = (snap.get('exposure') or {}).get('daily') or {}
    exposure_vals = []
    if isinstance(exposure_daily, dict):
        try:
            # sort by day key
            exposure_vals = [float(v) for _k, v in sorted(exposure_daily.items(), key=lambda kv: int(kv[0]))][-60:]
        except Exception:
            exposure_vals = []
    exposure_spark = _sparkline(exposure_vals, stroke="#276ef0") if exposure_vals else ""
    # Retrieval corpus growth sparkline (approx via sizes array if injected later)
    retrieval_sizes = (snap.get('retrieval') or {}).get('corpus_sizes') or []
    corpus_series = []
    if isinstance(retrieval_sizes, list):
        try:
            corpus_series = [int(v[1]) for v in retrieval_sizes if isinstance(v, (list, tuple)) and len(v) == 2][-60:]
        except Exception:
            corpus_series = []
    retrieval_corpus_spark = _sparkline(corpus_series, stroke="#8a2be2") if corpus_series else ""
    retrieval_failovers = 0
    try:
        from core import metrics as _m  # type: ignore
        gauge = getattr(_m, 'RETRIEVAL_PROVIDER_FAILOVER_TOTAL', None)
        if gauge and hasattr(gauge, '_value'):
            retrieval_failovers = int(getattr(gauge._value, 'get', lambda:0)())  # type: ignore
    except Exception:
        retrieval_failovers = 0
    # ---------------- Governance Weight Adjustments (JSONL direct parse best-effort) ----------------
    weight_adjust_recent = []  # list of dict
    weight_reason_counts = {}
    weight_last_summary = None
    weight_delta_spark = ""
    try:
        log_path = Path('audit/TEMPORAL_WEIGHT_ADJUST_LOG.jsonl')
        if log_path.exists():
            lines = log_path.read_text(encoding='utf-8').splitlines()[-120:]
            parsed = []
            for ln in lines:
                try:
                    obj = json.loads(ln)
                    if isinstance(obj, dict):
                        parsed.append(obj)
                except Exception:
                    continue
            # sort by ts
            try:
                parsed.sort(key=lambda o: o.get('ts') or 0)
            except Exception:
                pass
            # reason counts
            for o in parsed:
                rc = o.get('reason_code') or 'unknown'
                weight_reason_counts[rc] = weight_reason_counts.get(rc, 0) + 1
            # recent subset for table
            tail = parsed[-15:]
            for o in tail:
                weight_adjust_recent.append({
                    'ts': o.get('ts'),
                    'age_s': (time.time() - float(o.get('ts') or 0.0)),
                    'direction': o.get('direction'),
                    'delta': o.get('delta'),
                    'composite': o.get('composite'),
                    'reason_code': o.get('reason_code'),
                })
            if parsed:
                last = parsed[-1]
                weight_last_summary = f"Last decision: {last.get('reason_code')} delta={last.get('delta')} composite={last.get('composite')} ({'shadow' if last.get('shadow') else 'active'})"
            # sparkline of deltas (absolute) preserving sign visually with offset
            deltas = [float(o.get('delta') or 0.0) for o in parsed[-60:]]
            if deltas:
                # shift all by +min if negative present to keep relative pattern; or render signed separately
                mn = min(deltas)
                if mn < 0:
                    shifted = [d - mn for d in deltas]
                else:
                    shifted = deltas
                weight_delta_spark = _sparkline(shifted, stroke="#444")
    except Exception:
        pass

    # Order reason counts descending
    weight_reason_counts_sorted = sorted(weight_reason_counts.items(), key=lambda kv: kv[1], reverse=True)

    # Scanner stats (best-effort)
    scanner_open_counts = {"CRITICAL":0,"HIGH":0,"MEDIUM":0,"LOW":0}
    scanner_last_scan_ts = None
    remediation_spark = ""
    remediation_days_to_zero = None
    remediation_slope = None
    last_scan_latency = None
    avg_scan_latency = None
    catalog_available = True
    retrieval_quality = {}
    try:
        from scanner.scanner_agent import _FINDINGS  # type: ignore
        try:
            from scanner.scanner_agent import _LAST_SCAN_LATENCY, _AVG_SCAN_LATENCY  # type: ignore
            last_scan_latency = _LAST_SCAN_LATENCY
            avg_scan_latency = _AVG_SCAN_LATENCY
        except Exception:
            pass
        for f in _FINDINGS.values():
            sev = getattr(f, 'risk_severity', None) or getattr(f, 'severity', None) or 'UNKNOWN'
            sev = str(sev).upper()
            if sev in scanner_open_counts and getattr(f, 'status', 'open') in {'open','in_progress'}:
                scanner_open_counts[sev] += 1
            ts_attr = getattr(f, 'last_risk_calc_ts', None) or getattr(f, 'detected_ts', None)
            if ts_attr:
                try:
                    ts_epoch = ts_attr.timestamp()
                    if (scanner_last_scan_ts or 0) < ts_epoch:
                        scanner_last_scan_ts = ts_epoch
                except Exception:
                    pass
        # Load remediation burn-down series (best-effort)
        try:
            rpath = Path('artifacts/remediation_timeseries.json')
            if rpath.exists():
                rdata = json.loads(rpath.read_text(encoding='utf-8'))
                series = rdata.get('series') or []
                totals = [int(p.get('total_open',0)) for p in series][-60:]
                if totals:
                    remediation_spark = _sparkline(totals, stroke="#d33")
                remediation_slope = rdata.get('slope_per_day')
                remediation_days_to_zero = rdata.get('est_days_to_zero')
        except Exception:
            pass
    except Exception:
        pass
    # Retrieval quality metrics
    try:
        from core.retrieval.interface import _RETRIEVAL_METRICS  # type: ignore
        rq = _RETRIEVAL_METRICS.copy()
        retrieval_quality = {
            "avg_overlap_precision": rq.get("avg_overlap_precision"),
            "topk_drift": rq.get("topk_drift"),
        }
    except Exception:
        retrieval_quality = {}
    # Catalog presence warning
    try:
        cat_path = Path('artifacts/vuln_catalog_seed.json')
        if not cat_path.exists() or not cat_path.read_text(encoding='utf-8').strip():
            catalog_available = False
    except Exception:
        catalog_available = False
    # Risk factor contributions (best-effort)
    risk_factor_summary = {"avg_shares": {}, "top": [], "sparklines": {}}
    try:
        rf_path = Path('artifacts/risk_factor_contributions.json')
        if rf_path.exists():
            rdata = json.loads(rf_path.read_text(encoding='utf-8'))
            shares = (rdata or {}).get('avg_shares') or {}
            # Param for top-N
            top_n = 6
            try:
                from config.runtime_params import get_param as _getp  # type: ignore
                val = _getp('vuln.risk.ui.top_factors')
                if val is not None:
                    top_n = max(1, min(12, int(val)))
            except Exception:
                pass
            top_items = sorted(shares.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
            risk_factor_summary = {
                "avg_shares": shares,
                "top": [{"factor": k, "share": v} for k, v in top_items],
                "samples": rdata.get('samples'),
                "sparklines": {},
            }
            # Build history-based sparklines per factor
            hist_path = Path('artifacts/risk_factor_contributions.history.jsonl')
            if hist_path.exists():
                try:
                    lines = hist_path.read_text(encoding='utf-8').splitlines()[-120:]
                    hist_objs = []
                    import math as _math
                    for ln in lines:
                        try:
                            obj = json.loads(ln)
                            if isinstance(obj, dict):
                                hist_objs.append(obj)
                        except Exception:
                            continue
                    # For each top factor compute series
                    for k,_v in top_items:
                        series = []
                        for o in hist_objs:
                            try:
                                share = (o.get('avg_shares') or {}).get(k)
                                if share is None:
                                    continue
                                series.append(float(share))
                            except Exception:
                                continue
                        if series:
                            risk_factor_summary['sparklines'][k] = _sparkline(series, width=100, height=24, stroke="#555")
                except Exception:
                    pass
    except Exception:
        pass

    tpl = env.get_template('executive_summary.html')
    # ---------------- Enrichment Coverage (EPSS/KEV) ----------------
    enrichment_coverage = snap.get('enrichment_coverage') or {}
    if not enrichment_coverage:
        # Fallback: compute from DB if available
        try:
            total_rows = await postgres.fetch("SELECT count(*) FROM vulnerabilities")
            epss_rows = await postgres.fetch("SELECT count(*) FROM vulnerabilities WHERE epss IS NOT NULL")
            kev_rows = await postgres.fetch("SELECT count(*) FROM vulnerabilities WHERE kev_listed = true")
            total_v = int(total_rows[0][0]) if total_rows else 0
            epss_c = int(epss_rows[0][0]) if epss_rows else 0
            kev_c = int(kev_rows[0][0]) if kev_rows else 0
            enrichment_coverage = {
                "epss_pct": (epss_c / total_v) * 100 if total_v else 0.0,
                "kev_pct": (kev_c / total_v) * 100 if total_v else 0.0,
                "total": total_v,
                "epss_count": epss_c,
                "kev_count": kev_c,
            }
        except Exception:
            enrichment_coverage = {"epss_pct": 0.0, "kev_pct": 0.0}
    # Coverage trend (history JSONL sparkline best-effort)
    coverage_trend_svg = ""
    try:
        hist_path = Path('artifacts/enrichment_coverage.history.jsonl')
        if hist_path.exists():
            lines = hist_path.read_text(encoding='utf-8').splitlines()[-120:]
            kev_series = []
            for ln in lines:
                try:
                    obj = json.loads(ln)
                    kev_series.append(float(obj.get('kev_pct') or 0.0))
                except Exception:
                    continue
            if kev_series:
                # 7-sample EMA smoothing for presentation
                def _ema(vals: list[float], n: int = 7) -> list[float]:
                    if not vals:
                        return []
                    k = 2.0 / (n + 1)
                    out: list[float] = []
                    prev = vals[0]
                    out.append(prev)
                    for v in vals[1:]:
                        prev = v * k + prev * (1.0 - k)
                        out.append(prev)
                    return out
                smoothed = _ema(kev_series[-60:], 7)
                coverage_trend_svg = _sparkline(smoothed, width=120, height=30, stroke="#00897b")
    except Exception:
        coverage_trend_svg = ""
    # ---------------- Anomaly Surrogate Metrics ----------------
    anomaly_surrogates = {}
    anomaly_surrogate_sparklines = {"overlap": "", "snn_unique": "", "suppression": ""}
    try:
        # Prefer live executive aggregator for freshest metrics
        from core.main import executive_agg  # type: ignore
        esnap = executive_agg.snapshot()  # type: ignore[attr-defined]
        fusion = esnap.get("fusion") or {}
        anomaly_surrogates = {
            "overlap_ratio_avg": fusion.get("overlap_ratio_avg"),
            "snn_unique_ratio_avg": fusion.get("snn_unique_ratio_avg"),
            "suppression_rate_avg": fusion.get("suppression_rate_avg"),
        }
        # Build short trend lines from internal deques if available
        try:
            overlap_series = list(getattr(executive_agg, 'fusion_overlap', []))[-60:]
            snn_series = list(getattr(executive_agg, 'snn_unique', []))[-60:]
            suppress_series = list(getattr(executive_agg, 'suppression_rate', []))[-60:]
            if overlap_series:
                anomaly_surrogate_sparklines["overlap"] = _sparkline([float(v) for v in overlap_series], width=100, height=24, stroke="#2c7")
            if snn_series:
                anomaly_surrogate_sparklines["snn_unique"] = _sparkline([float(v) for v in snn_series], width=100, height=24, stroke="#a67")
            if suppress_series:
                anomaly_surrogate_sparklines["suppression"] = _sparkline([float(v) for v in suppress_series], width=100, height=24, stroke="#e67")
        except Exception:
            pass
    except Exception:
        # Best-effort; leave empty if unavailable
        anomaly_surrogates = {}
    html = tpl.render(
        snapshot=snap,
        generated_ts=time.time(),
        composite_sparkline=composite_spark,
        temporal_weight_sparkline=temporal_spark,
        retrieval_failovers=retrieval_failovers,
        exposure_sparkline=exposure_spark,
        retrieval_corpus_sparkline=retrieval_corpus_spark,
        weight_last_summary=weight_last_summary,
        weight_reason_counts=weight_reason_counts_sorted,
        weight_adjust_recent=weight_adjust_recent,
        weight_delta_sparkline=weight_delta_spark,
        scanner_open_counts=scanner_open_counts,
        scanner_last_scan_ts=scanner_last_scan_ts,
        remediation_sparkline=remediation_spark,
        remediation_slope=remediation_slope,
        remediation_days_to_zero=remediation_days_to_zero,
        last_scan_latency=last_scan_latency,
        avg_scan_latency=avg_scan_latency,
        catalog_available=catalog_available,
        retrieval_quality=retrieval_quality,
        risk_factor_summary=risk_factor_summary,
        enrichment_coverage=enrichment_coverage,
        enrichment_coverage_trend=coverage_trend_svg,
        anomaly_surrogates=anomaly_surrogates,
        anomaly_surrogate_sparklines=anomaly_surrogate_sparklines,
    )
    return html

__all__ = ['render_executive_summary']
