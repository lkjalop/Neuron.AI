# Changelog

All notable changes will be documented in this file. Versioning follows Semantic Versioning.

## [Unreleased]
### Added
- Graph feature extraction scaffold, snapshot & link prediction endpoints (`/api/v1/graph/*`).
- Background periodic feature refresh task (env `GRAPH_FEATURE_REFRESH_SEC`).
- Graph unification utility ingesting exposure graph snapshot.
- Link prediction endpoint extended with negative sampling (`negatives` param).
- Risk overlay features added to finding nodes (risk_channel.* attributes).
- Exposure ingestion endpoint (`POST /api/v1/graph/ingest-exposure`).
- Periodic persistence of runtime graph + features to `artifacts/runtime_graph.json`.
- Embedding prototype (random-walk Node2Vec-lite) with endpoints `/api/v1/graph/train-embeddings` & `/api/v1/graph/embedding/{node_id}`.

### Changed

### Deprecated

### Performance

### Testing

### Documentation

## [0.1.0] - 2025-09-07
### Added
- Governance recommendations endpoint `/governance/recommendations/recent`.
- Diagnostics frontend page `frontend/diagnostics.html` with normalization health chip.
- OpenAPI export script `docs/export_openapi.py` and initial `docs/API_REFERENCE.md`.
- SNN normalization alert rule and mapping age metric guard.
### Security / Tooling
- Initial security baseline scaffolding (OKRs pending integration).

## [0.2.0] - 2025-09-15
### Added
- Control Coverage Matrix section in generated Vulnerability Assessment Report (PDF) aggregating mapped controls and CWE references.
- Enrichment resolver support for EPSS scores (avg latest per CVE) and KEV catalog presence.
- Priority scoring formula now includes control weight, EPSS score, and KEV bonus (configurable via env vars: `CONTROL_WEIGHT_COEFF`, `EPSS_COEFF`, `KEV_BONUS`).
- Bulk enrichment endpoint `POST /api/vuln/findings/enrichment/bulk` (max 200 IDs).
- Frontend enrichment side panel (auto-creates on click of any element with `data-finding-id`).
- Prometheus metrics: `neuron_enrichment_resolve_seconds`, `neuron_priority_score_distribution`.
- Migration 0014: EPSS (`epss_scores`) and KEV (`kev_cves`) tables.
### Documentation
- New `ENRICHMENT_EXTENSIONS.md` detailing resolver output, priority model, control matrix, bulk endpoint, metrics.
### Tests
- Control matrix section test (`test_document_control_matrix.py`).
- Bulk enrichment API test (`test_bulk_enrichment_api.py`).

## [0.3.0] - 2025-09-18
### Added
- MITRE ATT&CK technique integration via `control_mitre_map` (migration 0015) with per-control and aggregated technique listings in enrichment output.
- Remediation Guidance Appendix ("APPENDIX A") in VA PDF summarizing control priorities and MITRE coverage.
- EPSS trend endpoints: aggregate (`/api/assessments/enrichment/epss_trend`) & raw (`/api/assessments/enrichment/epss_trend_raw`) with in‑memory TTL caching.
- Delta enrichment cache refresh endpoint (`POST /api/vuln/findings/enrichment/cache/delta_refresh`) with safety cap + force override.
- Frontend EPSS 7‑day sparkline visualization in assessments UI.
- Grafana dashboard `enrichment_insights.json` (latency, cache hit ratio, delta refresh impact, priority score distribution, EPSS averages, MITRE coverage).
### Changed
- PDF generator now disables content stream compression to enable lightweight test validation of appendix content.
### Tests
- `test_enrichment_mitre_mapping.py`, `test_delta_refresh_cap.py`, `test_report_appendix_generation.py` plus EPSS trend caching validations.
### Documentation
- Expanded `ENRICHMENT_EXTENSIONS.md` with Phase 3 features; added MITRE mapping, delta refresh semantics, EPSS trend endpoints, appendix details.
- New `MITRE_MAPPING.md` detailing ATT&CK integration model & usage.
### Notes
- Safety cap default (5000) override via `ENRICHMENT_DELTA_REFRESH_CAP`.
- Future enhancements queued: metrics emission expansion & deeper PDF structural assertions.
