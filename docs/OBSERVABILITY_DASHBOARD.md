# Observability & Grafana Dashboard

This document describes the Prometheus metrics exposed by the local vulnerability scanner and how they are visualized in the starter Grafana dashboard (`vuln_overview.json`).

## Metrics Inventory

### Scan Pipeline
- `scan_cycle_latency_seconds` (Histogram)
  - End-to-end latency of a full scan cycle (risk recompute + persistence + metrics emission).
  - Use `histogram_quantile` for p95/p99. Baseline target: < 5s p95 for small SBOMs.

### Risk Factor Attribution
- `risk_factor_share_percent{factor="<name>"}` (Gauge, gated by runtime param)
  - Average percent contribution of each risk factor across all current vulnerabilities at last recompute.
  - Track shifts indicating model weight/config changes or data drifts (e.g., EPSS spike events).

### SBOM Diff Intelligence
- `sbom_diff_component_churn_total` (Counter)
  - Cumulative count of components changed (added + removed) across SBOM diff ingestions.
- `sbom_diff_new_vulns_total` (Counter)
  - Cumulative new vulnerabilities surfaced directly attributable to component additions/updates.
- `sbom_diff_requests_total{status="success|error"}` (Counter)
  - Request outcome classification for the diff ingestion endpoint.

### Retrieval Quality
(Gated by runtime param `retrieval.metrics.enable`)
- `retrieval_overlap_precision` (Gauge)
  - Proxy recall/precision signal: token overlap ratio for retrieval sets.
- `retrieval_topk_drift` (Gauge)
  - Measures set difference volatility between successive top-k retrieval results (0.0 = stable, 1.0 = total churn).

### Daily Assessment Analytics
- `daily_assessment_slope` (Gauge)
  - Rolling slope (linear regression) of remediation burn‑down or weighted risk score trajectory.
- `daily_assessment_eta_days` (Gauge)
  - Estimated days to reach target (e.g., near-zero critical vulns) based on current slope.
- `daily_assessment_generated_total` (Counter)
  - Total count of nightly assessment artifacts generated.

### Remediation / Lifecycle
- `vuln_time_to_fix_seconds` (Histogram placeholder)
  - Future: distribution of time between vulnerability first observation and marked fixed (requires remediation workflow events).

### Reporting
- `report_pdf_generation_total{status="success|error"}` (Counter placeholder)
  - PDF generation outcome tally (placeholder until integrated with generator error handling block).

## Runtime Gating Parameters
To limit cardinality and optional overhead, these flags (from runtime params) control metric emission:
- `vuln.metrics.factors.enable` → Enables `risk_factor_share_percent` gauges.
- `retrieval.metrics.enable` → Enables retrieval quality gauges.
- `vuln.risk.ui.top_factors` → Limits factor list in UI (dashboard still shows all emitted factors).

## Dashboard Panels
1. Scan Cycle Latency p95 (Stat) – Uses `histogram_quantile(0.95, sum(rate(scan_cycle_latency_seconds_bucket[5m])) by (le))`.
2. Latency Distribution (TimeSeries) – Bucket rate visualization for tail amplification.
3. SBOM Diff New Vulns (Stat) – `increase(sbom_diff_new_vulns_total[5m])` to show recent ingestion impact.
4. SBOM Diff Churn (TimeSeries) – `increase(sbom_diff_component_churn_total[1h])` for structural change awareness.
5. Risk Factor Shares (Stacked % TimeSeries) – Direct view into shifting model weight impact.
6. Retrieval Overlap Precision – Stability & quality of document retrieval subsystem.
7. Retrieval TopK Drift – Detects volatility suggesting index staleness or noise.
8. Daily Assessment Slope – Trend direction of remediation progress.
9. Assessment ETA Days – Executive forecast of time to target state.
10. Assessments Generated (24h) – Operational heartbeat for nightly job.

## Alerting Recommendations (Future State)
| Condition | Expression | Rationale |
|-----------|------------|-----------|
| Scan latency high | `histogram_quantile(0.95, sum(rate(scan_cycle_latency_seconds_bucket[10m])) by (le)) > 10` | Scanner performance regression |
| Retrieval drift spike | `retrieval_topk_drift > 0.6` for 3 consecutive scrapes | Possible index corruption or unexpected content shift |
| Factor dominance anomaly | `max_over_time(risk_factor_share_percent{factor="exploit_active"}[1h]) > 60` | Exploit-driven portfolio risk spike |
| SBOM diff surge | `increase(sbom_diff_component_churn_total[30m]) > 500` | Large deployment / supply chain event |
| Nightly assessment stall | `increase(daily_assessment_generated_total[26h]) == 0` | Background scheduler failure |

## Extending the Dashboard
Add panels for:
- Remediation burn-down curve (when remediation event tracking implemented).
- PDF generation success rate once metric integrated.
- Time to Fix histogram (once lifecycle events exist).
- Automation triggers & anomaly detection (Batch E).
- Predictive estimations (Batch F): time-to-remediation forecast, exploit likelihood timeline.

## Operational Notes
- Retention: Prometheus retention set to `15d` (adjust via compose command flag `--storage.tsdb.retention.time`).
- Cardinality: Avoid unbounded labels; all current metrics avoid dynamic labels beyond factor name (bounded set derived from risk model factors).
- Importing Dashboard: Auto-provisioned under the root folder; update JSON and redeploy container for edits.
- Secure Credentials: Default Grafana admin creds are `admin/admin` in compose—change for any shared environment.

## Update Workflow
1. Modify or add metrics in `core/metrics.py`.
2. Reference new metrics in dashboard JSON under `grafana/dashboards`.
3. Recreate or `docker compose up -d --force-recreate grafana` to apply.

## Troubleshooting
- No data in panels: Confirm `/metrics` endpoint accessible inside network; `curl app:8000/metrics` from Prometheus container.
- Factor shares missing: Ensure runtime param `vuln.metrics.factors.enable` is set to true; confirm risk recompute executed.
- Retrieval gauges flatlined: Either disabled by gating or retrieval interface not invoked—check application logs.

---
Initial version – will evolve with Batch E (automation) & Batch F (predictive) enhancements.
