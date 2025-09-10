# Reporting & Dashboard Enhancements (Batch 20/21 Consolidation)

Generated: {{DATE_PLACEHOLDER}}

## Overview
Enhancements deliver richer executive visibility, export surfaces, adaptive governance visualization, and optional PDF artifact generation.

## New / Updated Endpoints

### Read-Only (Predict API Key Required)
- `GET /dashboard/snapshot` – Unified snapshot (governance, exposure, vulnerability, retrieval, anomaly surrogates). Multi-tenant placeholder via `tenant` query param.
- `GET /export/findings.csv` – Tabular vulnerability findings (id, cve_id, risk_score, severity, state, asset_id, last_seen).
- `GET /export/exposure_components.csv` – Vulnerability node components extracted from latest exposure graph (severity + base risk subset).
- `GET /export/control_gaps.csv` – Technique nodes lacking mapped control edges (control gap candidates).

### Admin (Admin API Key Required)
- `POST /admin/report/generate` – Builds unified report bundle (`bundle.json`, optional HTML, diff). Params:
  - `include_html` (bool, default true)
  - `include_pdf` (bool, default false; attempts WeasyPrint conversion if library present)
- `POST /admin/report/pdf` – Convenience wrapper always generating HTML then best-effort PDF.

Access control refinements decouple read-only analytical consumption (predict key) from mutation / generation (admin key).

## Unified Report Bundle Expansion
File: `artifacts/report_bundle/bundle.json`
New sections:
- `vulnerabilities`:
  - `severity_distribution`
  - `exploit_availability`
  - `top_findings` (best-effort; requires `artifacts/findings_recent.json` presence)
- `exposure`:
  - `total_risk`
  - `control_gaps` (list of technique IDs)
  - `risk_by_severity` (aggregated base risk by severity)
  - `trend_daily` (array of `[epoch_day, total_risk]` last ~60 days if available)
- `retrieval`:
  - `provider_failovers_total`
  - `corpus_sizes` (array `[index_timestamp, postings_count]` from last 20 retrieval index artifacts)
- `remediation`:
  - `open_findings_total`
  - `open_findings_delta` (vs previous bundle if available)
- `anomaly_surrogates`:
  - `overlap_ratio_avg`
  - `snn_unique_ratio_avg`
  - `suppression_rate_avg`

Existing keys retained:
- `generated_ts`
- `executive_kpis`
- `coverage` (attack matrix summary)

## Executive Summary HTML Additions
Template: `reports/templates/executive_summary.html`
Added inline SVG sparklines:
- Governance Composite (recent)
- Temporal Weight Adjustments
- Exposure Trend (daily risk)
- Retrieval Corpus Growth (approx doc+chunk postings count)

Metadata:
- Retrieval provider failover total displayed.

## Sparkline Generation
Implemented in `reports/generator.py` via `_sparkline(values)` – simple polyline over normalized range with configurable stroke colors:
- Composite: `#2c7`
- Temporal weight: `#c72`
- Exposure: `#276ef0`
- Retrieval corpus: `#8a2be2`

## PDF Generation (Optional)
If `weasyprint` is installed, `/admin/report/generate` with `include_pdf=true` or `/admin/report/pdf` will emit a PDF alongside the HTML (`executive_summary.pdf`). Best-effort; failure to import WeasyPrint silently skips PDF (artifacts still succeed). No additional runtime param required.

## Access Control Summary
| Endpoint | Scope | Key | Notes |
|----------|-------|-----|-------|
| `/dashboard/snapshot` | read-only | Predict | Multi-tenant placeholder |
| `/export/*.csv` | read-only | Predict | Findings & exposure exports |
| `/admin/report/generate` | admin | Admin | Bundle build & optional PDF |
| `/admin/report/pdf` | admin | Admin | Convenience HTML+PDF |

Rate limiting continues to use existing per-scope token bucket logic.

## Remediation Delta Logic
`remediation.open_findings_delta` compares current total open findings sum (across severities) with previous bundle snapshot (if `bundle.json` existed). Acts as a coarse remediation velocity indicator.

## Anomaly Surrogate Metrics
Surfaced from fusion snapshot averages to provide early precision/exposure balance proxies without full anomaly detail exposure.

## Follow-Up Opportunities
- Persist explicit exposure daily history rather than relying on aggregator internal map.
- Add retrieval quality metrics (window coverage ratio trend, enrichment attach success ratio sparkline).
- Include risk burn-down forecasting & SLA breach countdown sparkline.
- Multi-tenant true isolation for snapshots (shard aggregator windowed metrics per tenant).

## Batch 20 / 21 Summary
Batch 20 (Retrieval & Incremental RAG):
- Incremental sync endpoint `/rag/sync` with drift-triggered temporal weight dampening.
- Retrieval context attach with provenance hash validation.
- Metrics: provider failovers, drift adjustments, window coverage.

Batch 21 (Governance & Exposure & Reporting):
- Governance composite signal + adaptive temporal weight governor integration.
- Exposure graph simulation endpoint & risk tracking.
- Dashboard snapshot, CSV exports, sparklines, unified report bundle expansion.
- Optional PDF artifact generation.
- Access control refinement separating read-only analytical from admin mutation scopes.

## Usage Examples
### Generate Report (HTML + PDF)
```
curl -X POST -H "x-api-key: $ADMIN_API_KEY" "http://localhost:8000/admin/report/generate?include_html=true&include_pdf=true"
```

### Download Findings CSV (Read-Only)
```
curl -H "x-api-key: $PREDICT_API_KEY" "http://localhost:8000/export/findings.csv" -o findings.csv
```

### Fetch Snapshot
```
curl -H "x-api-key: $PREDICT_API_KEY" "http://localhost:8000/dashboard/snapshot"
```

## Integrity & Diffing
Each invocation writes `artifacts/report_bundle/bundle.json`; subsequent runs compute shallow diff vs prior (added/removed/changed keys) and record via `record_report_diff` hook if available.

---
This document will evolve as additional visualization and remediation analytics are added.
