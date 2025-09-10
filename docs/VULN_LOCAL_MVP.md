# Local Vulnerability Scanner MVP

This document describes the zero-budget local vulnerability scanning slice: ingest an SBOM, match against a small local catalog, compute basic risk, and visualize status in the executive summary.

## Components
- Catalog seed: `artifacts/vuln_catalog_seed.json` (simple entries: component name, affected version spec, severity, CVE id).
- SBOM ingestion endpoint: `POST /vuln/ingest_sbom` (CycloneDX or SPDX minimal subset).
- Scanner loop: background task (`scanner.scanner_agent.scanner_loop`) performing:
  1. External feed normalization (if enabled) – best‑effort.
  2. Local catalog match vs. last ingested SBOM snapshot (`artifacts/last_ingested_sbom.json`).
  3. Risk scoring (thin slice: severity weight + exploit/KEV placeholders) or catalog risk scoring shim.
  4. Burn‑down timeseries update (`artifacts/remediation_timeseries.json`).
- Executive HTML: `/ui/executive` (embedded panel shows open findings, burn‑down sparkline, scan latency, manual SBOM upload).
- Findings list UI: `/ui/findings` (sortable/filterable HTML view).
- Manual trigger: `POST /vuln/scan/trigger` (runs a one‑off scan cycle, returns summary).

## Quick Start
1. Start the API (ensure `vuln.scan.enabled=1` param or set via admin param update endpoint).
2. Verify catalog seed exists:
   - File: `artifacts/vuln_catalog_seed.json`
   - Add entries or adjust severities as needed.
3. Ingest an SBOM (example CycloneDX minimal):
```json
{
  "asset_name": "sample-app",
  "document": {
    "bomFormat": "CycloneDX",
    "components": [
      {"name": "openssl", "version": "3.0.13", "purl": "pkg:openssl/openssl@3.0.13"},
      {"name": "zlib", "version": "1.2.11", "purl": "pkg:zlib/zlib@1.2.11"}
    ]
  }
}
```
`curl -H "x-api-key: $KEY" -H "Content-Type: application/json" -d @sbom.json http://localhost:8000/vuln/ingest_sbom`

4. Trigger manual scan (optional to avoid waiting for interval):
`curl -X POST -H "x-api-key: $KEY" http://localhost:8000/vuln/scan/trigger`

5. Open Executive Summary: `http://localhost:8000/ui/executive` – view scanner panel.
6. Open Findings view: `http://localhost:8000/ui/findings` – validate matched CVEs and severities.

## Risk Model (MVP)
- Severity (CRITICAL, HIGH, MEDIUM, LOW) -> base risk buckets.
- Exploit / KEV placeholders add small bonuses if flagged in feed normalization.
- Future expansions: EPSS weighting, asset exposure multiplier, anomaly correlation, predictive emergence probability (placeholders already scaffolded in code).

## Burn-down Timeseries
File: `artifacts/remediation_timeseries.json`
Structure:
```json
{
  "series": [ {"day": 20250906, "total_open": 3, "CRITICAL": 1, "HIGH": 1, "MEDIUM": 1, "LOW": 0 } ],
  "slope_per_day": -0.5,
  "est_days_to_zero": 6.0
}
```
- `day` is floor(epoch/86400).
- Slope computed via simple least squares over index positions.
- `est_days_to_zero` only appears when slope < 0.

## Validation Harness
Run: `python scripts/validate_scanner_local.py --api-key $KEY`
- Shrinks scan interval temporarily, ingests test SBOM, polls for expected CVEs.

## Common Issues
| Symptom | Cause | Fix |
|---------|-------|-----|
| No matches show | Catalog seed missing | Create `artifacts/vuln_catalog_seed.json` |
| Burn-down sparkline empty | Only one day datapoint | Wait 24h or simulate older `day` entries |
| Latency shows n/a | No scan completed yet | Trigger manual scan |
| Findings risk_score null | Risk recompute pending | Wait next cycle or manual trigger |

## Next Evolution (Deferred)
- Retrieval quality metrics for context enrichment.
- PDF export hardening.
- Advanced risk: exploit probability modeling, dynamic asset exposure graph.

---
Document version: 2025-09-06
