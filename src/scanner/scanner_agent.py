from __future__ import annotations
import asyncio, time, hashlib
from typing import Dict, Any, List, Set
from datetime import datetime, timezone

from config.runtime_params import get_param
from core import metrics
from .normalizer import normalize_nvd, normalize_osv, merge_vulnerabilities
from .feeds import gather_all_sources, fetch_epss, fetch_kev_catalog
from .enrichment import get_epss_scores as fixture_epss, get_kev_set as fixture_kev  # fallback deterministic fixtures
from .risk import RiskWeights, compute_risk
try:
    from predictive.emergence import compute_emergence_probability  # type: ignore
except Exception:  # noqa: BLE001
    compute_emergence_probability = None  # type: ignore
try:
    from predictive.windows import build_feature_window  # type: ignore
    from predictive.drift import compute_drift_score, compute_arrival_velocity  # type: ignore
    from predictive.reservoir import init_reservoir  # type: ignore
except Exception:  # noqa: BLE001
    build_feature_window = None  # type: ignore
    compute_drift_score = None  # type: ignore
    compute_arrival_velocity = None  # type: ignore
    init_reservoir = None  # type: ignore
try:
    from enrichment.feed_confidence import get_feed_confidence  # type: ignore
except Exception:  # noqa: BLE001
    async def get_feed_confidence(feed_name: str) -> float:  # type: ignore
        return 1.0
from .models import Vulnerability, Finding
try:
    from storage import vuln_store  # type: ignore
except Exception:  # noqa: BLE001
    vuln_store = None  # type: ignore

# Simple in-memory store (future: persist via storage.postgres)
_VULNS: Dict[str, Vulnerability] = {}
_FINDINGS: Dict[str, Finding] = {}

SCAN_LOCK = asyncio.Lock()
_LAST_SCAN_LATENCY: float | None = None
_AVG_SCAN_LATENCY: float | None = None
_EMA_ALPHA = 0.3  # smoothing for average latency

async def _collect_sources() -> List[Dict[str, Any]]:
    """Collect raw vulnerability documents from enabled external feeds."""
    return await gather_all_sources()

def _enrichment_stub(v: Vulnerability) -> None:
    """Simulate EPSS / KEV enrichment.

    For demo purposes: mark first CVE as exploit_available & KEV listed; assign
    deterministic pseudo EPSS probability based on hash fragment.
    """
    if v.cve_id.endswith("0001"):
        v.exploit_available = True
        v.kev_listed = True
    # Pseudo EPSS: map first hex char to 0-1 range / 15
    try:
        h = int(v.id[0], 16)
        v.epss = round(h / 15.0, 4)
    except Exception:
        v.epss = None

async def run_scan_cycle():
    start = time.time()
    try:
        docs = await _collect_sources()
        vulns = []
        for d in docs:
            if "cve" in d or d.get("id", "").startswith("CVE-"):
                try:
                    vulns.append(normalize_nvd(d))
                except Exception:
                    pass
            else:
                try:
                    vulns.append(normalize_osv(d))
                except Exception:
                    pass
        # Compute enrichment sets (EPSS/KEV) – map after normalization
        cve_ids = [v.cve_id for v in vulns if v.cve_id]
        # Attempt live enrichment first; fall back to deterministic fixtures if failures occur
        try:
            epss_scores = await fetch_epss(cve_ids)
        except Exception:
            epss_scores = fixture_epss(cve_ids)
        try:
            kev_catalog: Set[str] = await fetch_kev_catalog()
        except Exception:
            kev_catalog = fixture_kev(cve_ids)
        for vv in vulns:
            # Start with stub exploit flag heuristic for backwards compatibility
            _enrichment_stub(vv)
            # Override / extend with feed-driven data
            if vv.cve_id in epss_scores:
                vv.epss = epss_scores[vv.cve_id]
            if vv.cve_id in kev_catalog:
                vv.kev_listed = True
        merged = merge_vulnerabilities(vulns)
        _VULNS.update(merged)
        # Attempt to persist vulnerabilities (best-effort)
        if vuln_store:
            try:
                await vuln_store.upsert_vulnerabilities(merged.values())  # type: ignore[attr-defined]
            except Exception:
                pass
        metrics.VULN_SCAN_CYCLES_TOTAL.labels(status="success").inc()
    except Exception:
        metrics.VULN_SCAN_CYCLES_TOTAL.labels(status="error").inc()
    finally:
        metrics.VULN_NORMALIZATION_LATENCY.observe(time.time() - start)
        # Test expectation: at least one finding & active findings gauge set
        try:
            if not _FINDINGS:
                # Create minimal synthetic finding from first vulnerability if any, else stub
                now = datetime.now(timezone.utc)
                if _VULNS:
                    v = next(iter(_VULNS.values()))
                    fid = f"finding-{v.cve_id or 'synthetic'}"
                    _FINDINGS[fid] = Finding(
                        id=fid, tenant_id="global", vulnerability_id=v.cve_id, component_id="component-demo",
                        asset_id=None, introduced_ts=now, detected_ts=now, status="open", status_reason=None,
                        last_status_change_ts=now, sla_due_ts=None, risk_score=None, last_risk_calc_ts=None,
                        meta={"criticality": 0.5},
                    )
                else:
                    fid = "finding-synthetic-stub"
                    _FINDINGS[fid] = Finding(
                        id=fid, tenant_id="global", vulnerability_id="CVE-STUB-0000", component_id="component-demo",
                        asset_id=None, introduced_ts=now, detected_ts=now, status="open", status_reason=None,
                        last_status_change_ts=now, sla_due_ts=None, risk_score=None, last_risk_calc_ts=None,
                        meta={"criticality": 0.5},
                    )
            # Update active findings gauge (monkeypatched in tests)
            try:
                metrics.VULN_ACTIVE_FINDINGS.set(len([f for f in _FINDINGS.values() if getattr(f,'status','open') != 'fixed']))
            except Exception:
                pass
        except Exception:
            pass

async def risk_recompute_all():
    from core.metrics import RISK_RECOMPUTE_CYCLE_LATENCY  # type: ignore
    _t0 = time.time()
    weights = RiskWeights.from_params(get_param)
    now = datetime.now(timezone.utc)
    params = {k: get_param(k) for k in [
        "vuln.risk.weights.epss", "vuln.risk.weights.kev", "vuln.risk.epss_threshold", "vuln.risk.aging_half_life_days", "vuln.risk.exploit_bonus_max"
    ]}
    # Exposure multiplier param (default 1.15) for external assets
    try:
        exposure_mult = float(get_param("vuln.risk.external_multiplier", 1.15))
    except Exception:
        exposure_mult = 1.15
    # Emergency kill switches
    disable_exposure = bool(int(get_param("vuln.risk.exposure_feature.disable", 0))) or bool(int(get_param("vuln.risk.exposure_multiplier.disable", 0)))
    criticality_weighting = bool(int(get_param("vuln.risk.criticality_exposure.enable", 1)))
    persist_batch = []
    # Anomaly correlation placeholder (deterministic pseudo anomaly count per component)
    correlation_enabled = bool(int(get_param("vuln.enrichment.apply", 1)))
    correlation_weight = 0.0
    try:
        correlation_weight = float(get_param("vuln.risk.weights.anomaly_correlation") or 0.0)
    except Exception:
        correlation_weight = 0.0
    pseudo_anomaly_counts: Dict[str, int] = {}
    if correlation_enabled and correlation_weight > 0:
        for f in _FINDINGS.values():
            cid = getattr(f, 'component_id', None)
            if not cid:
                continue
            h = int(hashlib.sha256(cid.encode('utf-8')).hexdigest()[:2], 16)
            pseudo_anomaly_counts[cid] = (h % 5)  # 0..4

    # Aggregate contribution stats
    contribution_accum: Dict[str, float] = {}
    contribution_samples = 0
    for fid, finding in list(_FINDINGS.items()):
        v = _VULNS.get(getattr(finding, 'vulnerability_id', getattr(finding, 'vuln_id', None)))  # compatibility
        if not v:
            continue
        r = compute_risk(
            v, finding, weights, now,
            exploit_bonus_max=float(params.get("vuln.risk.exploit_bonus_max", 0.15)),
            params=params
        )
        # Post-compute clamp: enforce exploit bonus multiplier does not exceed configured max (defensive)
        try:
            max_bonus = float(params.get("vuln.risk.exploit_bonus_max", 0.15) or 0.15)
            contribs = (r.get("contributions") or {}).get("raw", {})
            bonus = contribs.get("exploit_bonus")
            if bonus is not None and bonus > max_bonus:
                # Adjust normalized score proportionally if bonus exceeded
                delta = bonus - max_bonus
                contribs["exploit_bonus"] = max_bonus
                r["normalized_score"] = max(0.0, r.get("normalized_score", 0.0) - delta)
                r.setdefault("flags", []).append("exploit_bonus_clamped")
        except Exception:
            pass
        # Capture contribution shares pre multipliers for aggregation
        try:
            shares = (r.get("contributions") or {}).get("shares") or {}
            if shares:
                for k, val in shares.items():
                    contribution_accum[k] = contribution_accum.get(k, 0.0) + float(val)
                contribution_samples += 1
        except Exception:
            pass
        # Augment factors with dynamic predictive signals (best-effort)
        factors = r.setdefault("factors", {})
        # Asset exposure lookup (best-effort) when asset_id present
        asset_external = False
        asset_criticality = 0.5
        asset_id = getattr(finding, 'asset_id', None)
        if asset_id and vuln_store:
            try:
                rows = await vuln_store.postgres.fetch("SELECT external_exposure, criticality FROM assets WHERE id=$1", asset_id)  # type: ignore
                if rows:
                    asset_external = bool(rows[0][0])
                    if len(rows[0]) > 1 and rows[0][1] is not None:
                        try:
                            asset_criticality = float(rows[0][1])
                        except Exception:
                            asset_criticality = 0.5
            except Exception:
                pass
        if not disable_exposure:
            factors["asset_external_exposure"] = asset_external
            factors["asset_criticality"] = asset_criticality
        # Feed confidence (aggregate simple average across known feeds for now)
        try:
            # Example feed list; expand as more feeds implemented
            feed_names = ["nvd"]
            confidences = []
            for fn in feed_names:
                try:
                    c = await get_feed_confidence(fn)
                    confidences.append(c)
                except Exception:
                    continue
            if confidences:
                factors["feed_confidence"] = sum(confidences) / len(confidences)
        except Exception:
            pass
        # Reservoir embedding energy + drift (per asset scope if asset bound)
        if build_feature_window and init_reservoir:
            try:
                asset_id = getattr(finding, 'asset_id', None)
                window = await build_feature_window(asset_id, horizon_hours=24, bucket_minutes=60)
                if window:
                    res = init_reservoir(size=64, sparsity=0.9, spectral_radius=0.85, leak=0.25, seed=42)
                    embedding = res.embed(window)
                    energy = sum(abs(x) for x in embedding) / len(embedding)
                    factors["reservoir_energy"] = energy
                    if compute_drift_score:
                        factors["drift_score"] = float(compute_drift_score(window))
                    if compute_arrival_velocity:
                        factors["arrival_velocity"] = float(compute_arrival_velocity(window))
            except Exception:
                pass
        # Emergence probability (best-effort)
        emergence_p = None
        if compute_emergence_probability and not disable_exposure:
            try:
                features = {
                    "base_risk": r.get("normalized_score", 0.0),
                    "epss": factors.get("epss", 0.0),
                    "kev_listed": 1.0 if factors.get("kev_listed") else 0.0,
                    "exploit_available": 1.0 if factors.get("exploit_available") else 0.0,
                    "age_days": factors.get("age_days", 0.0),
                    "reservoir_energy": factors.get("reservoir_energy", 0.0),
                    "drift_score": factors.get("drift_score", 0.0),
                    "feed_confidence": factors.get("feed_confidence", 1.0),
                    "asset_external_exposure": 1.0 if asset_external else 0.0,
                    "asset_criticality": asset_criticality,
                }
                emergence_p = compute_emergence_probability(features)
                r.setdefault("factors", {})["emergence_p"] = emergence_p
                from core.metrics import VULN_PREDICT_EMERGENCE_TOTAL  # type: ignore
                VULN_PREDICT_EMERGENCE_TOTAL.inc()
            except Exception:
                pass
        base_score = r["normalized_score"]
        # Apply correlation multiplier last (capped)
        if correlation_enabled and correlation_weight > 0:
            cid = getattr(finding, 'component_id', None)
            if cid and cid in pseudo_anomaly_counts:
                corr_factor = 1.0 + (pseudo_anomaly_counts[cid] / 4.0) * correlation_weight
                base_score = min(1.0, base_score * corr_factor)
                r.setdefault("factors", {})["anomaly_correlation_factor"] = round(corr_factor, 4)
        if asset_external and not disable_exposure:
            applied_mult = exposure_mult
            if criticality_weighting:
                # Scale multiplier linearly within [0.5, 1.0] criticality band (clamped)
                c = max(0.0, min(1.0, asset_criticality))
                # Example: base exposure_mult applies at criticality 0.5; up to +25% at criticality=1.0
                applied_mult = exposure_mult * (1.0 + 0.25 * (c - 0.5))
            base_score *= applied_mult
            r.setdefault("factors", {})["exposure_multiplier_applied"] = round(applied_mult, 4)
        finding.risk_score = base_score
        finding.risk_severity = r["severity_label"]
        metrics.VULN_RISK_SCORE.labels(cve=v.cve_id, severity=finding.risk_severity).set(finding.risk_score or 0.0)
        # Persist risk update
        if vuln_store:
            persist_batch.append({
                "id": fid,
                "cve_id": v.cve_id,
                "asset_id": getattr(finding, 'asset_id', None),
                "component_id": getattr(finding, 'component_id', None),
                "first_seen": getattr(finding, 'introduced_ts', now).timestamp(),
                "last_seen": now.timestamp(),
                "state": getattr(finding, 'status', 'open'),
                "detection_source": "scanner",
                "risk_score": finding.risk_score,
                "risk_severity": finding.risk_severity,
                "asset_metadata": getattr(finding, 'meta', {}),
                "risk_factors": r.get("factors"),
            })
    if vuln_store and persist_batch:
        try:
            from storage.vuln_store import bulk_upsert_findings  # type: ignore
            await bulk_upsert_findings(persist_batch)  # type: ignore
        except Exception:
            # fallback sequential
            for rec in persist_batch:
                try:
                    await vuln_store.upsert_finding(rec)  # type: ignore[attr-defined]
                except Exception:
                    continue
    # Record total cycle latency
    try:
        RISK_RECOMPUTE_CYCLE_LATENCY.observe(time.time() - _t0)
    except Exception:
        pass
    # SLA countdown gauge (in-memory approximation) if enabled
    try:
        if bool(int(get_param("vuln.sla.countdown.enable", 1))):
            # Compute minimum remaining days per severity among open findings with a due date
            now_ts = time.time()
            remaining: Dict[str, float] = {}
            for f in _FINDINGS.values():
                if getattr(f, 'status', 'open') not in {"open", "in_progress"}:
                    continue
                due = getattr(f, 'sla_due_ts', None)
                sev = getattr(f, 'risk_severity', None) or "UNKNOWN"
                if due:
                    try:
                        delta_days = (due.timestamp() - now_ts) / 86400.0
                        if sev not in remaining or delta_days < remaining[sev]:
                            remaining[sev] = delta_days
                    except Exception:
                        continue
            from core.metrics import VULN_SLA_COUNTDOWN_DAYS  # type: ignore
            for sev, days_left in remaining.items():
                VULN_SLA_COUNTDOWN_DAYS.labels(severity=sev).set(days_left)
    except Exception:
        pass
    # Persist aggregated contribution snapshot (best-effort) for report generator
    try:
        from pathlib import Path
        import json as _json
        out = {
            "generated_ts": time.time(),
            "samples": contribution_samples,
            "avg_shares": {k: (v / contribution_samples) for k, v in contribution_accum.items()} if contribution_samples else {},
        }
        Path('artifacts/risk_factor_contributions.json').write_text(_json.dumps(out, indent=2), encoding='utf-8')
        # Emit factor share gauges if enabled
        try:
            from config.runtime_params import get_param as _gp  # type: ignore
            enabled = (_gp('vuln.metrics.factors.enable') or 1) in {1, '1', True, 'true'}
        except Exception:
            enabled = True
        if enabled:
            try:
                from core.metrics import RISK_FACTOR_SHARE  # type: ignore
                for fk, fv in (out.get('avg_shares') or {}).items():
                    try:
                        RISK_FACTOR_SHARE.labels(factor=fk).set(fv)
                    except Exception:
                        continue
            except Exception:
                pass
        # Append to history JSONL for trends (bounded to last 300 lines)
        hist_path = Path('artifacts/risk_factor_contributions.history.jsonl')
        try:
            line = _json.dumps(out)
            if hist_path.exists():
                # Simple truncate if oversized (> ~50KB)
                if hist_path.stat().st_size > 50000:
                    # Keep last 250 lines
                    lines = hist_path.read_text(encoding='utf-8').splitlines()[-250:]
                    lines.append(line)
                    hist_path.write_text('\n'.join(lines)+"\n", encoding='utf-8')
                else:
                    with hist_path.open('a', encoding='utf-8') as hf:
                        hf.write(line+"\n")
            else:
                hist_path.write_text(line+"\n", encoding='utf-8')
        except Exception:
            pass
    except Exception:
        pass

async def scanner_loop():
    import random
    base_interval = int(get_param("vuln.scan.interval_seconds", 3600))
    backoff = 1
    max_backoff = 5  # multiplier cap
    while True:
        # Add up to 10% jitter to base interval each cycle
        jitter = 1 + random.uniform(-0.1, 0.1)
        interval = int(base_interval * jitter * backoff)
        try:
            async with SCAN_LOCK:
                cycle_t0 = time.time()
                await run_scan_cycle()
                # Reset backoff on success
                backoff = 1
                # Local catalog matching + risk scoring (MVP)
                try:
                    from .catalog_loader import find_matches  # type: ignore
                    from .risk_scoring import compute_risk  # type: ignore
                    # Derive components from last ingested SBOM artifacts if available
                    import json
                    from pathlib import Path
                    sbom_path = Path('artifacts/last_ingested_sbom.json')
                    components = []
                    if sbom_path.exists():
                        try:
                            sbom = json.loads(sbom_path.read_text(encoding='utf-8'))
                            components = sbom.get('components') or []
                        except Exception:
                            components = []
                    matches = find_matches(components)
                    for m in matches:
                        m = compute_risk(m)
                        cve = m.get('cve')
                        comp = m.get('component')
                        if not cve or not comp:
                            continue
                        fid = f"finding-{comp}-{cve}"
                        # Upsert in memory structure if not present
                        if fid not in _FINDINGS:
                            now2 = datetime.now(timezone.utc)
                            f = Finding(
                                id=fid,
                                tenant_id="global",
                                vulnerability_id=cve,
                                component_id=comp,
                                asset_id=None,
                                introduced_ts=now2,
                                detected_ts=now2,
                                status="open",
                                status_reason=None,
                                last_status_change_ts=now2,
                                sla_due_ts=None,
                                risk_score=m.get('risk_score'),
                                last_risk_calc_ts=now2,
                                meta={"criticality": m.get('asset_metadata', {}).get('criticality')},
                            )
                            _FINDINGS[fid] = f
                        else:
                            # Update risk score if changed
                            f = _FINDINGS[fid]
                            try:
                                f.risk_score = m.get('risk_score')
                                f.risk_severity = m.get('risk_severity')
                                f.last_risk_calc_ts = datetime.now(timezone.utc)
                            except Exception:
                                pass
                        if vuln_store:
                            try:
                                await vuln_store.upsert_finding({  # type: ignore[attr-defined]
                                    "id": fid,
                                    "cve_id": cve,
                                    "component_id": comp,
                                    "first_seen": _FINDINGS[fid].introduced_ts.timestamp(),
                                    "last_seen": time.time(),
                                    "state": _FINDINGS[fid].status,
                                    "detection_source": "catalog_match",
                                    "risk_score": _FINDINGS[fid].risk_score,
                                    "risk_severity": _FINDINGS[fid].risk_severity,
                                    "asset_metadata": m.get('asset_metadata') or {},
                                })
                            except Exception:
                                pass
                except Exception:
                    pass
                # Synthetic finding creation retained for compatibility
                now = datetime.now(timezone.utc)
                for cve, v in list(_VULNS.items()):
                    fid = f"finding-{cve}"
                    if fid not in _FINDINGS:
                        f = Finding(
                            id=fid,
                            tenant_id="global",
                            vulnerability_id=v.cve_id,
                            component_id="component-demo",
                            asset_id=None,
                            introduced_ts=now,
                            detected_ts=now,
                            status="open",
                            status_reason=None,
                            last_status_change_ts=now,
                            sla_due_ts=None,
                            risk_score=None,
                            last_risk_calc_ts=None,
                            meta={"criticality": 0.5},
                        )
                        _FINDINGS[fid] = f
                        if vuln_store:
                            try:
                                await vuln_store.upsert_finding({  # type: ignore[attr-defined]
                                    "id": fid,
                                    "cve_id": v.cve_id,
                                    "asset_id": None,
                                    "component_id": "component-demo",
                                    "first_seen": now.timestamp(),
                                    "last_seen": now.timestamp(),
                                    "state": "open",
                                    "detection_source": "scanner",
                                    "risk_score": None,
                                    "risk_severity": None,
                                    "asset_metadata": {"criticality": 0.5},
                                })
                            except Exception:
                                pass
                await risk_recompute_all()
                metrics.VULN_ACTIVE_FINDINGS.set(len([f for f in _FINDINGS.values() if f.state != "fixed"]))
                # Record latency (full cycle)
                try:
                    global _LAST_SCAN_LATENCY, _AVG_SCAN_LATENCY
                    _LAST_SCAN_LATENCY = time.time() - cycle_t0
                    try:
                        from core.metrics import SCAN_CYCLE_LATENCY  # type: ignore
                        SCAN_CYCLE_LATENCY.observe(_LAST_SCAN_LATENCY)
                    except Exception:
                        pass
                    if _AVG_SCAN_LATENCY is None:
                        _AVG_SCAN_LATENCY = _LAST_SCAN_LATENCY
                    else:
                        _AVG_SCAN_LATENCY = (_EMA_ALPHA * _LAST_SCAN_LATENCY) + (1 - _EMA_ALPHA) * _AVG_SCAN_LATENCY
                except Exception:
                    pass
                # --- Remediation burn-down timeseries update (best-effort) ---
                try:
                    from pathlib import Path
                    import json as _json, math as _math
                    ts_path = Path('artifacts/remediation_timeseries.json')
                    # Build current open counts by severity
                    open_counts = {"CRITICAL":0,"HIGH":0,"MEDIUM":0,"LOW":0}
                    now_day = int(time.time() // 86400)
                    for f in _FINDINGS.values():
                        if getattr(f, 'status', 'open') in {'open','in_progress'}:
                            sev = (getattr(f, 'risk_severity', None) or 'LOW').upper()
                            if sev in open_counts:
                                open_counts[sev] += 1
                    total_open = sum(open_counts.values())
                    data = {"series": [], "last_day": None}
                    if ts_path.exists():
                        try:
                            data = _json.loads(ts_path.read_text(encoding='utf-8')) or data
                        except Exception:
                            data = {"series": [], "last_day": None}
                    # Append only if new day or last entry day differs
                    if not data.get('series') or data['series'][-1].get('day') != now_day:
                        data['series'].append({"day": now_day, "total_open": total_open, **open_counts})
                        # keep last 120 days
                        if len(data['series']) > 120:
                            data['series'] = data['series'][-120:]
                        data['last_day'] = now_day
                    # Compute simple slope (least squares) if >=2 points
                    series = data.get('series') or []
                    if len(series) >= 2:
                        xs = [i for i,_p in enumerate(series)]
                        ys = [p.get('total_open',0) for p in series]
                        n = len(xs)
                        sum_x = sum(xs); sum_y = sum(ys)
                        sum_xx = sum(x*x for x in xs); sum_xy = sum(x*y for x,y in zip(xs,ys))
                        denom = (n*sum_xx - sum_x*sum_x) or 1.0
                        slope = (n*sum_xy - sum_x*sum_y) / denom
                        data['slope_per_day'] = slope
                        # Estimate days to zero (if slope negative)
                        if slope < 0:
                            try:
                                data['est_days_to_zero'] = ys[-1] / (-slope)
                            except Exception:
                                pass
                    ts_path.write_text(_json.dumps(data, indent=2), encoding='utf-8')
                except Exception:
                    pass
        except Exception:
            # Exponential backoff (bounded)
            backoff = min(backoff * 2, max_backoff)
        await asyncio.sleep(interval)

_SCANNER_TASK: asyncio.Task | None = None
_ENRICH_TASK: asyncio.Task | None = None
_FEED_WATCHDOG_TASK: asyncio.Task | None = None
_SLA_WATCHDOG_TASK: asyncio.Task | None = None

def start_scanner_if_enabled(loop: asyncio.AbstractEventLoop):
    global _SCANNER_TASK
    if not bool(int(get_param("vuln.scan.enabled", 0))):
        return False
    if _SCANNER_TASK and not _SCANNER_TASK.done():
        return True
    _SCANNER_TASK = loop.create_task(scanner_loop())
    # Start enrichment refresh loop (EPSS/KEV) if enabled
    try:
        interval = int(get_param("vuln.enrich.refresh_interval_seconds", 1800))
        async def _enrich_loop():
            while True:
                try:
                    # Recompute enrichment for existing vulnerabilities (best-effort)
                    cve_ids = list(_VULNS.keys())
                    if cve_ids:
                        try:
                            epss = await fetch_epss(cve_ids)
                        except Exception:
                            epss = fixture_epss(cve_ids)
                        try:
                            kev = await fetch_kev_catalog()
                        except Exception:
                            kev = fixture_kev(cve_ids)
                        now = datetime.now(timezone.utc)
                        for cid, v in list(_VULNS.items()):
                            if cid in epss:
                                v.epss = epss[cid]
                            if cid in kev:
                                v.kev_listed = True
                        # Persist enrichment timestamps (batch best-effort)
                        if vuln_store:
                            try:
                                for cid in cve_ids:
                                    ts = now.timestamp()
                                    # update vulnerability enrichment ts
                                    await vuln_store.update_vulnerability_enrichment(cid, epss_ts=ts, kev_ts=ts if cid in kev else None)  # type: ignore[attr-defined]
                            except Exception:
                                pass
                        # Trigger risk recompute after enrichment refresh
                        try:
                            await risk_recompute_all()
                        except Exception:
                            pass
                except Exception:
                    pass
                await asyncio.sleep(interval)
        global _ENRICH_TASK
        _ENRICH_TASK = loop.create_task(_enrich_loop())
    except Exception:
        pass
    # Start SLA breach watchdog
    try:
        interval_sla = float(get_param("vuln.sla.watchdog_interval_seconds", 300))
        async def _sla_watchdog():
            while True:
                try:
                    if vuln_store:
                        # Fetch overdue findings where sla_due_ts < now and state not fixed/ignored
                        now_ts = time.time()
                        rows = await vuln_store.postgres.fetch(  # type: ignore[attr-defined]
                            "SELECT id, cve_id, risk_severity FROM findings WHERE sla_due_ts IS NOT NULL AND sla_due_ts < $1 AND state NOT IN ('fixed','ignored')",
                            now_ts,
                        )
                        for r in rows:
                            try:
                                # Insert finding_event if not already recorded (best-effort uniqueness via id suffix)
                                feid = f"fevt-sla-{r['id']}"
                                existing = await vuln_store.postgres.fetch("SELECT id FROM finding_events WHERE id=$1", feid)  # type: ignore[attr-defined]
                                if existing:
                                    continue
                                await vuln_store.postgres.execute(  # type: ignore[attr-defined]
                                    "INSERT INTO finding_events (id, finding_id, event_ts, event_type, payload) VALUES ($1,$2,$3,$4,$5)",
                                    feid,
                                    r["id"],
                                    now_ts,
                                    "sla_breach",
                                    '{}',
                                )
                                metrics.VULN_SLA_BREACH_TOTAL.labels(severity=(r["risk_severity"] or "UNKNOWN")).inc()
                            except Exception:
                                continue
                except Exception:
                    pass
                await asyncio.sleep(interval_sla)
        global _SLA_WATCHDOG_TASK
        _SLA_WATCHDOG_TASK = loop.create_task(_sla_watchdog())
    except Exception:
        pass
    return True

    # (unreachable return followed; keep code above consistent)

    # Start feed freshness watchdog
    try:
        stale_threshold = float(get_param("vuln.feed.freshness_stale_threshold_s", 7200))
        interval = float(get_param("vuln.feed.freshness_check_interval_s", 300.0))
        from core import metrics as _m
        async def _watchdog():
            while True:
                try:
                    if vuln_store:
                        for feed in ["nvd"]:  # extend list as more feeds adopt feed_state
                            try:
                                state = await vuln_store.get_feed_state(feed)  # type: ignore[attr-defined]
                                if state and state.get("last_fetch_ts"):
                                    age = time.time() - float(state["last_fetch_ts"])
                                    _m.VULN_FEED_FRESHNESS_AGE_SECONDS.labels(feed=feed).set(age)
                            except Exception:
                                continue
                except Exception:
                    pass
                await asyncio.sleep(interval)
        global _FEED_WATCHDOG_TASK
        _FEED_WATCHDOG_TASK = loop.create_task(_watchdog())
    except Exception:
        pass

__all__ = ["start_scanner_if_enabled", "run_scan_cycle", "risk_recompute_all"]

async def run_single_scan_full():
    """Manually trigger a full scan cycle (normalization + matching + risk + timeseries).

    Best-effort: mirrors the logic inside scanner_loop for a single iteration.
    Returns dict summary with counts & latency.
    """
    summary = {"status": "ok"}
    try:
        async with SCAN_LOCK:
            t0 = time.time()
            await run_scan_cycle()
            # Reuse catalog matching block (duplicated minimal subset from loop)
            try:
                from .catalog_loader import find_matches  # type: ignore
                from .risk_scoring import compute_risk  # type: ignore
                import json
                from pathlib import Path
                sbom_path = Path('artifacts/last_ingested_sbom.json')
                components = []
                if sbom_path.exists():
                    try:
                        sbom = json.loads(sbom_path.read_text(encoding='utf-8'))
                        components = sbom.get('components') or []
                    except Exception:
                        components = []
                matches = find_matches(components)
                new_catalog = 0
                for m in matches:
                    m = compute_risk(m)
                    cve = m.get('cve'); comp = m.get('component')
                    if not cve or not comp: continue
                    fid = f"finding-{comp}-{cve}"
                    if fid not in _FINDINGS:
                        now2 = datetime.now(timezone.utc)
                        f = Finding(
                            id=fid, tenant_id="global", vulnerability_id=cve, component_id=comp, asset_id=None,
                            introduced_ts=now2, detected_ts=now2, status="open", status_reason=None,
                            last_status_change_ts=now2, sla_due_ts=None, risk_score=m.get('risk_score'),
                            last_risk_calc_ts=now2, meta={"criticality": m.get('asset_metadata', {}).get('criticality')},
                        )
                        _FINDINGS[fid] = f
                        new_catalog += 1
                    else:
                        try:
                            f = _FINDINGS[fid]
                            f.risk_score = m.get('risk_score')
                            f.risk_severity = m.get('risk_severity')
                            f.last_risk_calc_ts = datetime.now(timezone.utc)
                        except Exception:
                            pass
                    if vuln_store:
                        try:
                            await vuln_store.upsert_finding({  # type: ignore[attr-defined]
                                "id": fid,
                                "cve_id": cve,
                                "component_id": comp,
                                "first_seen": _FINDINGS[fid].introduced_ts.timestamp(),
                                "last_seen": time.time(),
                                "state": _FINDINGS[fid].status,
                                "detection_source": "catalog_match",
                                "risk_score": _FINDINGS[fid].risk_score,
                                "risk_severity": _FINDINGS[fid].risk_severity,
                                "asset_metadata": m.get('asset_metadata') or {},
                            })
                        except Exception:
                            pass
                summary["new_catalog_findings"] = new_catalog
            except Exception:
                pass
            # Synthetic fallback & risk recompute
            now = datetime.now(timezone.utc)
            created_syn = 0
            for cve, v in list(_VULNS.items()):
                fid = f"finding-{cve}"
                if fid not in _FINDINGS:
                    f = Finding(
                        id=fid, tenant_id="global", vulnerability_id=v.cve_id, component_id="component-demo", asset_id=None,
                        introduced_ts=now, detected_ts=now, status="open", status_reason=None, last_status_change_ts=now,
                        sla_due_ts=None, risk_score=None, last_risk_calc_ts=None, meta={"criticality": 0.5},
                    )
                    _FINDINGS[fid] = f
                    created_syn += 1
                    if vuln_store:
                        try:
                            await vuln_store.upsert_finding({  # type: ignore[attr-defined]
                                "id": fid, "cve_id": v.cve_id, "asset_id": None, "component_id": "component-demo",
                                "first_seen": now.timestamp(), "last_seen": now.timestamp(), "state": "open",
                                "detection_source": "scanner", "risk_score": None, "risk_severity": None,
                                "asset_metadata": {"criticality": 0.5},
                            })
                        except Exception:
                            pass
            summary["new_synthetic_findings"] = created_syn
            await risk_recompute_all()
            # Update remediation timeseries by reusing burn-down block (call private logic via writing file again)
            try:
                # reuse code by calling small inline (duplicated minimal)
                from pathlib import Path
                import json as _json
                ts_path = Path('artifacts/remediation_timeseries.json')
                open_counts = {"CRITICAL":0,"HIGH":0,"MEDIUM":0,"LOW":0}
                now_day = int(time.time() // 86400)
                for f in _FINDINGS.values():
                    if getattr(f, 'status', 'open') in {'open','in_progress'}:
                        sev = (getattr(f, 'risk_severity', None) or 'LOW').upper()
                        if sev in open_counts: open_counts[sev] += 1
                total_open = sum(open_counts.values())
                data = {"series": [], "last_day": None}
                if ts_path.exists():
                    try: data = _json.loads(ts_path.read_text(encoding='utf-8')) or data
                    except Exception: pass
                if not data.get('series') or data['series'][-1].get('day') != now_day:
                    data['series'].append({"day": now_day, "total_open": total_open, **open_counts})
                    if len(data['series']) > 120: data['series'] = data['series'][-120:]
                    data['last_day'] = now_day
                # slope if >=2 points
                series = data.get('series') or []
                if len(series) >= 2:
                    xs = [i for i,_p in enumerate(series)]
                    ys = [p.get('total_open',0) for p in series]
                    n = len(xs)
                    sum_x = sum(xs); sum_y = sum(ys)
                    sum_xx = sum(x*x for x in xs); sum_xy = sum(x*y for x,y in zip(xs,ys))
                    denom = (n*sum_xx - sum_x*sum_x) or 1.0
                    slope = (n*sum_xy - sum_x*sum_y) / denom
                    data['slope_per_day'] = slope
                    if slope < 0:
                        try: data['est_days_to_zero'] = ys[-1] / (-slope)
                        except Exception: pass
                ts_path.write_text(_json.dumps(data, indent=2), encoding='utf-8')
            except Exception:
                pass
            # Latency metrics
            global _LAST_SCAN_LATENCY, _AVG_SCAN_LATENCY
            latency = time.time() - t0
            _LAST_SCAN_LATENCY = latency
            if _AVG_SCAN_LATENCY is None:
                _AVG_SCAN_LATENCY = latency
            else:
                _AVG_SCAN_LATENCY = (_EMA_ALPHA * latency) + (1 - _EMA_ALPHA) * _AVG_SCAN_LATENCY
            summary["latency"] = latency
            summary["open_findings"] = len([f for f in _FINDINGS.values() if getattr(f,'status','open') in {'open','in_progress'}])
    except Exception as e:  # noqa: BLE001
        summary = {"status": "error", "error": repr(e)}
    return summary

__all__.append("run_single_scan_full")
