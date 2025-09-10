#!/usr/bin/env python
"""Generate Phase 3 evaluation gate report Markdown.

Aggregates:
- Baseline metrics (artifacts/eval/baseline_metrics.json if present)
- SNN sweep selection (artifacts/eval/snn_threshold_sweep.json)
- Threshold rationale doc hash
- Governance doc hashes (uplift & resource budget)
Outputs:
  artifacts/eval/gate_report_phase3.md
"""
from __future__ import annotations
import json, hashlib, pathlib, datetime, textwrap, re, urllib.request, argparse

BASELINE_FILE = pathlib.Path("artifacts/eval/baseline_metrics.json")
SNN_SWEEP_FILE = pathlib.Path("artifacts/eval/snn_threshold_sweep.json")
RATIONALE_FILE = pathlib.Path("docs/SNN_THRESHOLD_RATIONALE.md")
UPLIFT_FILE = pathlib.Path("docs/UPLIFT_TARGETS.md")
RESOURCE_FILE = pathlib.Path("docs/RESOURCE_BUDGET.md")
SOC_FILE = pathlib.Path("docs/SOC_TRAINING.md")
OUT_FILE = pathlib.Path("artifacts/eval/gate_report_phase3.md")

# Metric names of interest (keep narrow to avoid full parser dependency)
METRIC_PATTERNS = {
    'overlap_ratio': re.compile(r'^neuron_fusion_overlap_ratio\{tenant="(?P<tenant>[^"]+)"\} (?P<value>[-0-9.]+)$'),
    'snn_unique_ratio': re.compile(r'^neuron_fusion_snn_unique_ratio\{tenant="(?P<tenant>[^"]+)"\} (?P<value>[-0-9.]+)$'),
    'suppression_rate': re.compile(r'^neuron_fusion_suppression_rate\{tenant="(?P<tenant>[^"]+)"\} (?P<value>[-0-9.]+)$'),
    'suppression_alerts': re.compile(r'^neuron_fusion_suppression_alerts_total\{tenant="(?P<tenant>[^"]+)",strategy="(?P<strategy>[^"]+)"\} (?P<value>[-0-9.]+)$'),
}

def scrape_metrics(url: str) -> dict:
    out: dict[str, dict] = {k: {} for k in METRIC_PATTERNS}
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:  # nosec B310 (controlled internal call)
            for raw_line in resp.read().decode('utf-8', errors='ignore').splitlines():
                line = raw_line.strip()
                if not line or line.startswith('#'):
                    continue
                for key, pat in METRIC_PATTERNS.items():
                    m = pat.match(line)
                    if m:
                        d = m.groupdict()
                        tenant = d.get('tenant') or 'unknown'
                        value = float(d.get('value', '0') or 0)
                        if key == 'suppression_alerts':
                            strategy = d.get('strategy', '?')
                            out[key].setdefault(tenant, {})[strategy] = value
                        else:
                            out[key][tenant] = value
                        break
    except Exception:
        pass
    return out
INCIDENT_LOG = pathlib.Path("artifacts/eval/incidents.log")


def _hash(p: pathlib.Path) -> str:
    if not p.exists():
        return "missing"
    return hashlib.sha256(p.read_bytes()).hexdigest()

def load_json(p: pathlib.Path) -> dict:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main():
    parser = argparse.ArgumentParser(description="Generate Phase 3 evaluation gate report")
    parser.add_argument("--metrics-url", help="Optional Prometheus metrics endpoint URL (e.g. http://localhost:8000/metrics)")
    args = parser.parse_args()
    baseline = load_json(BASELINE_FILE)
    sweep = load_json(SNN_SWEEP_FILE)
    selected = sweep.get("selected", {})
    sel_thr = selected.get("threshold")
    rational_hash = _hash(RATIONALE_FILE)
    uplift_hash = _hash(UPLIFT_FILE)
    resource_hash = _hash(RESOURCE_FILE)
    soc_hash = _hash(SOC_FILE)

    def fmt(v):
        return "?" if v is None else (f"{v:.4f}" if isinstance(v, float) else str(v))

    baseline_section = "Baseline metrics not found." if not baseline else textwrap.dedent(f"""
    | Metric | Value |
    |--------|-------|
    | Precision | {fmt(baseline.get('precision'))} |
    | Recall | {fmt(baseline.get('recall'))} |
    | F1 | {fmt(baseline.get('f1'))} |
    | Anomalies | {fmt(baseline.get('predicted_anomaly_events'))} |
    """).strip()

    snn_section = "SNN sweep selection missing." if not selected else textwrap.dedent(f"""
    | Metric | Value |
    |--------|-------|
    | Threshold | {fmt(sel_thr)} |
    | Precision | {fmt(selected.get('snn', {}).get('precision'))} |
    | Recall | {fmt(selected.get('snn', {}).get('recall'))} |
    | F1 | {fmt(selected.get('snn', {}).get('f1'))} |
    | Recall Uplift | {fmt(selected.get('uplifts', {}).get('recall_uplift'))} |
    | Precision Loss | {fmt(selected.get('uplifts', {}).get('precision_loss'))} |
    | F1 Uplift | {fmt(selected.get('uplifts', {}).get('f1_uplift'))} |
    | Added p95 Latency (ms) | {fmt(selected.get('overhead', {}).get('added_latency_p95_ms'))} |
    | Decision | {fmt(selected.get('decision'))} |
    """).strip()

    # Incident aggregation (best-effort)
    incidents = []
    if INCIDENT_LOG.exists():
        try:
            lines = INCIDENT_LOG.read_text(encoding="utf-8").strip().splitlines()
            for line in lines[-500:]:  # cap parse effort
                try:
                    incidents.append(json.loads(line))
                except Exception:
                    continue
        except Exception:
            pass
    disable_cycles = [i for i in incidents if i.get("type") == "snn_disable_cycle"]
    total_inc = len(incidents)
    recent_disable = len(disable_cycles)
    max_cycles = max((i.get("cycles", 0) for i in disable_cycles), default=0)

    incidents_section = "No incidents logged." if not incidents else textwrap.dedent(f"""
    | Metric | Value |
    |--------|-------|
    | Total Incidents | {total_inc} |
    | Disable Cycle Incidents | {recent_disable} |
    | Max Cycles Observed | {max_cycles} |
    | Last Incident Type | {incidents[-1].get('type','?')} |
    | Last Incident Age (s) | {{age_last}} |
    """
    )
    if incidents:
        try:
            import time as _t
            age = int(_t.time() - incidents[-1].get("generated_ts", _t.time()))
            incidents_section = incidents_section.replace("{age_last}", str(age))
        except Exception:
            incidents_section = incidents_section.replace("{age_last}", "?")
    else:
        incidents_section = incidents_section.replace("{age_last}", "-")

    fusion_section = "Metrics URL not provided."  # default
    if args.metrics_url:
        metrics_data = scrape_metrics(args.metrics_url)
        # Build concise table for each tenant observed
        tenants = sorted(set(list(metrics_data['overlap_ratio'].keys()) + list(metrics_data['suppression_rate'].keys())))
        rows = ["| Tenant | Overlap Ratio | SNN Unique Ratio | Suppression Rate | Alerts (strategy->count) |", "|--------|---------------|------------------|------------------|----------------------------|"]
        for t in tenants:
            overlap_v = metrics_data['overlap_ratio'].get(t)
            snn_unique_v = metrics_data['snn_unique_ratio'].get(t)
            supp_rate = metrics_data['suppression_rate'].get(t)
            alerts_map = metrics_data['suppression_alerts'].get(t, {}) if isinstance(metrics_data['suppression_alerts'], dict) else {}
            alerts_fmt = ", ".join(f"{k}:{int(v)}" for k, v in sorted(alerts_map.items())) or "-"
            def fmtf(v):
                return "-" if v is None else f"{v:.3f}"
            rows.append(f"| {t} | {fmtf(overlap_v)} | {fmtf(snn_unique_v)} | {fmtf(supp_rate)} | {alerts_fmt} |")
        fusion_section = "\n".join(rows)

    report = f"""# Phase 3 Gate Report (SNN Prototype)
Generated: {datetime.datetime.utcnow().isoformat()}Z

## 1. Governance Doc Hashes
| Document | SHA256 |
|----------|--------|
| UPLIFT_TARGETS.md | {uplift_hash} |
| RESOURCE_BUDGET.md | {resource_hash} |
| SNN_THRESHOLD_RATIONALE.md | {rational_hash} |
| SOC_TRAINING.md | {soc_hash} |

## 2. Baseline Reference
{baseline_section}

## 3. SNN Selected Threshold & Performance
{sel_thr if sel_thr is not None else 'N/A'}

{snn_section}

## 4. Conformance Summary
- Recall uplift target met? {'YES' if selected.get('uplifts', {}).get('recall_uplift', 0) >= 0.15 else 'NO'}
- Precision loss within limit? {'YES' if selected.get('uplifts', {}).get('precision_loss', 1) <= 0.05 else 'NO'}
- Added p95 latency <5ms? {'YES' if selected.get('overhead', {}).get('added_latency_p95_ms', 999) < 5 else 'NO'}
- Resource footprint within budget? {'YES' if selected.get('resources_snapshot', {}).get('rss_delta_mb', 999) < 25 else 'NO'}

## 5. Risk Notes
See rationale + SOC training docs for failure modes (precision flood, silent suppression, latency exhaustion). Resource guard & schema caps active.

## 6. Firefighter Incident Summary
{incidents_section}

## 7. Next Actions
If all conformance items YES => proceed to fusion planning (Phase 4 prep). Else open tuning/retire review.

## 8. Fusion & Suppression (Live Metrics Snapshot)
Source: {args.metrics_url or 'N/A'}

{fusion_section}

--
Integrity: Hash this file upon generation if used for gate closure.
"""
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(report, encoding="utf-8")
    print(f"Wrote {OUT_FILE}")

if __name__ == "__main__":
    main()
