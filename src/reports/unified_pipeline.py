"""Unified Report Pipeline (skeleton).

Aggregates generation of multiple report artifacts (JSON, HTML, coverage,
KPI snapshot) into a single callable for scheduling or on-demand export.
"""
from __future__ import annotations

import json, time
try:
    from observability.tracing import span  # type: ignore
except Exception:  # pragma: no cover
    from contextlib import contextmanager as _cm
    def span(name: str, **tags):  # type: ignore
        @_cm
        def _s():
            yield
        return _s()
from pathlib import Path
from typing import Dict, Any

try:
    from reports.generator import render_executive_summary  # type: ignore
except Exception:  # pragma: no cover
    async def render_executive_summary():  # type: ignore
        return "<html><body><p>summary unavailable</p></body></html>"

try:
    from core.main import executive_agg  # type: ignore
except Exception:  # pragma: no cover
    class _Dummy:
        def snapshot(self):
            return {}
    executive_agg = _Dummy()  # type: ignore

try:
    from coverage.attack_matrix import coverage_summary  # type: ignore
except Exception:  # pragma: no cover
    def coverage_summary():  # type: ignore
        return {}

try:
    from core.fusion_weight_audit import record_report_diff  # type: ignore
except Exception:  # pragma: no cover
    def record_report_diff(diff):  # type: ignore
        return None

ARTIFACT_DIR = Path("artifacts/report_bundle")


def _load_previous(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {}


def _diff(prev: Dict[str, Any], cur: Dict[str, Any]) -> Dict[str, Any]:
    diff: Dict[str, Any] = {"added": {}, "removed": {}, "changed": {}}
    prev_keys = set(prev.keys())
    cur_keys = set(cur.keys())
    for k in cur_keys - prev_keys:
        diff["added"][k] = cur[k]
    for k in prev_keys - cur_keys:
        diff["removed"][k] = prev[k]
    for k in prev_keys & cur_keys:
        pv, cv = prev[k], cur[k]
        if pv != cv:
            # For nested dicts do shallow changed detection only
            diff["changed"][k] = {"previous": pv, "current": cv}
    return diff


async def build_report_bundle(include_html: bool = True, include_diff: bool = True) -> Dict[str, Any]:
    with span("report.bundle", html=include_html, diff=include_diff):
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        snapshot = executive_agg.snapshot() if hasattr(executive_agg, "snapshot") else {}
        coverage = coverage_summary()
        # ---------------- Governance Temporal Weight Adjustments (aggregation) ----------------
        weight_adjustments: Dict[str, Any] = {}
        try:
            log_path = Path("audit/TEMPORAL_WEIGHT_ADJUST_LOG.jsonl")
            if log_path.exists():
                lines = log_path.read_text(encoding="utf-8").splitlines()[-200:]  # tail last 200 adjustments
                recs = []
                counts: Dict[str, int] = {}
                for ln in lines:
                    try:
                        obj = json.loads(ln)
                        if not isinstance(obj, dict):
                            continue
                        recs.append({
                            "ts": obj.get("ts"),
                            "direction": obj.get("direction"),
                            "delta": obj.get("delta"),
                            "reason_code": obj.get("reason_code"),
                            "composite": obj.get("composite"),
                            "shadow": obj.get("shadow"),
                        })
                        rc = obj.get("reason_code") or "unknown"
                        counts[rc] = counts.get(rc, 0) + 1
                    except Exception:
                        continue
                # Sort recent by timestamp if present
                try:
                    recs.sort(key=lambda r: (r.get("ts") or 0))
                except Exception:
                    pass
                weight_adjustments = {
                    "recent": recs[-25:],  # keep last 25 for bundle brevity
                    "counts": counts,
                    "total_records_sampled": len(recs),
                    "last_reason_code": recs[-1]["reason_code"] if recs else None,
                }
        except Exception:
            weight_adjustments = {}
        # ---------------- Vulnerability Detail Section (best-effort) ----------------
        vuln_detail: Dict[str, Any] = {}
        try:
            # Severity distribution & exploit availability already expected in snapshot if upstream populated
            if snapshot:
                vuln_detail["severity_distribution"] = snapshot.get("vulnerability_severity") or {}
                vuln_detail["exploit_availability"] = snapshot.get("vulnerability_exploit_available") or {}
            # Load recent findings file if exists (lightweight augmentation)
            findings_path = Path("artifacts/findings_recent.json")
            if findings_path.exists():
                try:
                    raw_findings = json.loads(findings_path.read_text(encoding="utf-8"))
                    if isinstance(raw_findings, list):
                        # Top CVEs by risk_score
                        top = sorted(raw_findings, key=lambda r: r.get("risk_score", 0), reverse=True)[:25]
                        vuln_detail["top_findings"] = [{k: v for k, v in f.items() if k in {"id","cve_id","risk_score","risk_severity","last_seen","state"}} for f in top]
                except Exception:
                    pass
        except Exception:
            vuln_detail = {}

        # ---------------- Exposure Section ----------------
        exposure: Dict[str, Any] = {}
        try:
            exposure_graph_path = Path("artifacts/exposure_graph.json")
            if exposure_graph_path.exists():
                eg = json.loads(exposure_graph_path.read_text(encoding="utf-8"))
                exposure["total_risk"] = eg.get("total_risk")
                nodes = eg.get("nodes", [])
                # Technique coverage & control gaps
                tech_nodes = [n for n in nodes if n.get("type") == "technique"]
                control_edges = {e.get("dst") for e in eg.get("edges", []) if e.get("type") == "control-technique"}
                gaps = [t.get("id") for t in tech_nodes if t.get("id") not in control_edges]
                exposure["control_gaps"] = gaps[:100]
                # Aggregate risk by severity (for vuln nodes)
                sev_agg: Dict[str, float] = {}
                for n in nodes:
                    if n.get("type") == "vuln":
                        sev = (n.get("severity") or "UNKNOWN").upper()
                        try:
                            sev_agg[sev] = sev_agg.get(sev, 0.0) + float(n.get("base_risk") or 0.0)
                        except Exception:
                            continue
                exposure["risk_by_severity"] = {k: round(v, 4) for k, v in sev_agg.items()}
            # Exposure trend (daily buckets) from snapshot
            exposure_trend = []
            try:
                exp_daily = (snapshot.get("exposure") or {}).get("daily" ) or {}
                if not exp_daily and hasattr(executive_agg, "exposure_daily"):
                    # Access internal if available
                    exp_daily = getattr(executive_agg, "exposure_daily", {})  # type: ignore[attr-defined]
                if isinstance(exp_daily, dict):
                    # Convert epoch day -> value sorted ascending
                    exposure_trend = sorted([[int(k), float(v)] for k, v in exp_daily.items()], key=lambda x: x[0])[-60:]
            except Exception:
                exposure_trend = []
            exposure["trend_daily"] = exposure_trend
        except Exception:
            exposure = {}

        # ---------------- Retrieval Stats Section ----------------
        retrieval: Dict[str, Any] = {}
        try:
            # Provider failover count (counter; approximate by reading metric value best-effort)
            from core import metrics as _m  # type: ignore
            failovers = 0
            try:
                counter = getattr(_m, 'RETRIEVAL_PROVIDER_FAILOVER_TOTAL', None)
                if counter and hasattr(counter, '_value'):
                    failovers = int(getattr(counter._value, 'get', lambda:0)())  # type: ignore
            except Exception:
                pass
            retrieval["provider_failovers_total"] = failovers
            # Corpus size approximation from artifacts/retrieval index (count unique doc+chunk pairs)
            corpus_dir = Path("artifacts/retrieval")
            corpus_sizes = []
            if corpus_dir.exists():
                for fp in sorted(corpus_dir.glob("index_*.json"))[-20:]:  # last 20 indices
                    try:
                        data = json.loads(fp.read_text(encoding="utf-8"))
                        total = 0
                        if isinstance(data, dict):
                            for postings in data.values():
                                if isinstance(postings, list):
                                    total += len(postings)
                        corpus_sizes.append([int(fp.stem.split('_')[-1]), total])
                    except Exception:
                        continue
            retrieval["corpus_sizes"] = corpus_sizes
        except Exception:
            retrieval = {}

        # ---------------- Remediation Delta Section ----------------
        remediation: Dict[str, Any] = {}
        try:
            # Compare open findings counts 7d vs 30d if available in snapshot
            open_sev = snapshot.get("open_findings_severity") or {}
            # Placeholder deltas; real implementation would diff previous bundle
            prev_open = 0
            if isinstance(open_sev, dict):
                prev_open = sum(int(v) for v in open_sev.values())
            remediation["open_findings_total"] = prev_open
            # If previous bundle exists, compute delta
            prev_bundle_path = ARTIFACT_DIR / "bundle.json"
            if prev_bundle_path.exists():
                try:
                    prev_bundle = json.loads(prev_bundle_path.read_text(encoding="utf-8"))
                    prev_open_prev = 0
                    op = (prev_bundle.get("executive_kpis") or {}).get("open_findings_severity") or {}
                    if isinstance(op, dict):
                        prev_open_prev = sum(int(v) for v in op.values())
                    remediation["open_findings_delta"] = prev_open - prev_open_prev
                except Exception:
                    pass
        except Exception:
            remediation = {}

        # ---------------- Anomaly Surrogate Metrics Section ----------------
        anomaly_surrogates: Dict[str, Any] = {}
        try:
            fusion = snapshot.get("fusion") or {}
            anomaly_surrogates["overlap_ratio_avg"] = fusion.get("overlap_ratio_avg")
            anomaly_surrogates["snn_unique_ratio_avg"] = fusion.get("snn_unique_ratio_avg")
            anomaly_surrogates["suppression_rate_avg"] = fusion.get("suppression_rate_avg")
        except Exception:
            anomaly_surrogates = {}

        # ---------------- Forensics Evidence Summary ----------------
        forensics_summary: Dict[str, Any] = {}
        try:
            from core.forensics import jobs as fj  # type: ignore
            jobs = fj.list_jobs(limit=100)
            modality_counts: Dict[str, int] = {}
            last_job_ts = 0.0
            for j in jobs:
                modality_counts[j.modality] = modality_counts.get(j.modality, 0) + 1
                try:
                    last_job_ts = max(last_job_ts, float(j.submitted_ts or 0.0))
                except Exception:
                    pass
            forensics_summary = {
                "job_counts": modality_counts,
                "last_job_ts": last_job_ts or None,
            }
        except Exception:
            forensics_summary = {}
        # ---------------- Hunt Events Summary (cache JSON if present) ----------------
        hunt_summary: Dict[str, Any] = {}
        try:
            hunt_cache = Path("artifacts/hunt_events.json")
            if hunt_cache.exists():
                h = json.loads(hunt_cache.read_text(encoding="utf-8"))
                if isinstance(h, list):
                    hunt_summary["total_events"] = len(h)
                    # basic stats: by type if field present
                    by_type: Dict[str, int] = {}
                    for rec in h:
                        t = str((rec or {}).get("type") or "unknown")
                        by_type[t] = by_type.get(t, 0) + 1
                    hunt_summary["by_type"] = by_type
        except Exception:
            hunt_summary = {}

        # ---------------- Enrichment Coverage (EPSS/KEV) ----------------
        enrichment_coverage: Dict[str, Any] = {}
        try:
            # Prefer snapshot if already present
            if snapshot and isinstance(snapshot, dict):
                enrichment_coverage = snapshot.get("enrichment_coverage") or {}
            if not enrichment_coverage:
                # Attempt to compute from scanner store; fallback to 0s
                epss_count = kev_count = total = 0
                try:
                    from scanner.scanner_agent import _VULNS as _SC_VULNS  # type: ignore
                    for v in _SC_VULNS.values():
                        total += 1
                        try:
                            if getattr(v, 'epss', None) is not None:
                                epss_count += 1
                            if bool(getattr(v, 'kev_listed', False)):
                                kev_count += 1
                        except Exception:
                            continue
                except Exception:
                    pass
                enrichment_coverage = {
                    "total": total,
                    "epss_count": epss_count,
                    "kev_count": kev_count,
                    "epss_pct": (epss_count / total) * 100 if total else 0.0,
                    "kev_pct": (kev_count / total) * 100 if total else 0.0,
                }
        except Exception:
            enrichment_coverage = {}

        bundle = {
            "generated_ts": time.time(),
            "executive_kpis": snapshot,
            "coverage": coverage,
            "enrichment_coverage": enrichment_coverage,
            "vulnerabilities": vuln_detail,
            "exposure": exposure,
            "retrieval": retrieval,
            "remediation": remediation,
            "anomaly_surrogates": anomaly_surrogates,
            "weight_adjustments": weight_adjustments,
            "forensics": forensics_summary,
            "hunt": hunt_summary,
        }
        json_path = ARTIFACT_DIR / "bundle.json"
        prev = _load_previous(json_path) if include_diff else {}
        json_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        html_path = None
        if include_html:
            with span("report.render_html"):
                html = await render_executive_summary()
            html_path = ARTIFACT_DIR / "executive_summary.html"
            html_path.write_text(html, encoding="utf-8")
        out: Dict[str, Any] = {"json": str(json_path), "html": str(html_path) if html_path else None}
        if include_diff:
            with span("report.diff"):
                diff_obj = _diff(prev, bundle)
                out["diff"] = diff_obj
                try:
                    record_report_diff(diff_obj)
                except Exception:
                    pass
        return out


__all__ = ["build_report_bundle"]
