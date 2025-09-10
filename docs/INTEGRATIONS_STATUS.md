# External Integrations Status

Date: 2025-09-07

This document summarizes current readiness, architecture hooks, and roadmap for external security platform integrations.

## Overview
The platform is instrumented to export anomalies, vulnerability signals, and governance actions. A new metric `neuron_integration_export_total` (`INTEGRATION_EXPORT_TOTAL`) provides cardinality for export attempts by integration name and outcome.

| Integration | Current State | Implemented Hooks | Gaps / TODO | Target Outcomes |
|-------------|---------------|-------------------|-------------|-----------------|
| Splunk (SIEM) | Planned (scaffold) | Metrics foundation, anomaly retrieval endpoints, audit logs | Need outbound HTTP handler (`/integrations/splunk/export`), token/config storage, retry/backoff | Forward anomalies & governance events to Splunk index, enable search macros |
| ServiceNow (ITSM/Ticketing) | Planned | Ticket generation scaffolds (see `ticket_generator.py`), audit chain | Need dedicated incident creation module, SLA breach mapping, state sync (close/update) | Auto-create incidents for SLA breaches & critical anomalies |
| CrowdStrike (EDR/Threat Intel) | Planned | Threat feed ingestion skeleton (threat fetch metrics) | Need CrowdStrike API client, IOC normalization mapping, enrichment pipeline insertion | Enrich anomalies with endpoint process & reputation context |
| Cyberstash (Threat Intelligence) | Planned | Threat feed metrics (`THREAT_FEED_*`) | Need fetch adapter, de-dup logic, feed to enrichment stage, caching/backoff policy | Additional indicator context & dynamic suppression signals |

## Data Flow Hooks
1. Ingestion -> Detection -> Fusion -> Enrichment -> Anomaly Sink
2. Export Layer (TBD): pluggable dispatchers per integration using a common interface:
   - `prepare_payload(anomaly|finding)`
   - `send(payload, credentials)` with retry + circuit breaker
   - Metrics: increment `INTEGRATION_EXPORT_TOTAL{integration, outcome}` and latency histogram (future `*_latency_seconds`).

## Metrics Mapping
| Concern | Existing Metric | Integration Usage |
|---------|-----------------|-------------------|
| Export cardinality | `INTEGRATION_EXPORT_TOTAL` | Per integration attempt tracking |
| Anomaly volume | `neuron_anomalies_total` | Sizing ingestion / rate limits |
| Unique coverage | `neuron_hopfield_unique_ratio`, `neuron_fusion_snn_unique_ratio_rolling` | Selective export or prioritization |
| SLA breaches | `neuron_vuln_sla_breach_total`, `neuron_vuln_sla_breach_active` | ServiceNow incident triggers |
| Rotation / governance | `neuron_repository_rotations_total`, `neuron_governance_actions_total` | Operational dashboards in Splunk |
| Threat feeds | `neuron_threat_feed_status_total`, `neuron_threat_feed_age_seconds` | CrowdStrike / Cyberstash pipeline health |

## Configuration & Secrets (Planned)
Runtime params or environment variables will gate each integration:
- `integration.splunk.enabled`, `integration.servicenow.enabled`, etc.
- Secure credential injection via environment or secrets manager path (not persisted to audit logs).
- Backoff parameters: `integration.<name>.backoff_initial_s`, `integration.<name>.backoff_max_s`.

## Proposed Module Structure
```
core/
  integrations/
    base.py          # IExporter interface (export(record)->ExportResult)
    splunk.py        # SplunkHECExporter
    servicenow.py    # ServiceNowIncidentExporter
    crowdstrike.py   # CrowdStrikeIntelClient/Exporter
    cyberstash.py    # CyberstashFeedAdapter
```
Dispatcher registration occurs at startup; disabled exporters skipped.

## Export Reliability Roadmap
| Phase | Feature | Description |
|-------|---------|-------------|
| 1 | Basic fire-and-forget | Simple POST, count metrics |
| 2 | Retry + backoff | Exponential backoff, jitter, max attempts |
| 3 | Circuit breaker | Open on consecutive failures; cooldown timer |
| 4 | Dead-letter queue | Persist failed payloads for replay |
| 5 | Adaptive filtering | Suppress low-value exports under load (use unique ratios) |

## Governance & Filtering Concepts
- Use `hopfield_unique` and SNN unique ratios to label anomalies with novelty score for prioritization.
- Export policy runtime params:
  - `integration.export.max_rps`
  - `integration.export.min_severity`
  - `integration.export.require_novelty` (bool) -> only send anomalies with unique detector contribution.

## Audit Integration
Existing audit files:
- `audit/PERFORMANCE_TIER_SWITCH.jsonl`
- `audit/REPOSITORY_ROTATIONS.jsonl`
- `audit/param_changes.log`

Planned audit for exports:
- `audit/INTEGRATION_EXPORTS.jsonl` lines: `{ts, integration, outcome, latency_ms, retry_count}`

## Minimal Exporter Interface (Draft)
```python
class ExportResult(TypedDict):
    outcome: str  # success|error|skipped|disabled
    status_code: int | None
    latency_s: float
    error: str | None

class IExporter(Protocol):
    name: str
    enabled: Callable[[], bool]
    def export(self, record: dict) -> ExportResult: ...
```

## Next Implementation Steps
1. Create `core/integrations/base.py` with interface + registry.
2. Implement Splunk HEC exporter (config: URL, token, verify_ssl, batch size optional).
3. Add export hook in anomaly sink flush path.
4. Emit `INTEGRATION_EXPORT_TOTAL` + append audit line.
5. Add retry/backoff + minimal circuit breaker (stateful in exporter instance).
6. Add config endpoint `/integrations/status` summarizing enabled exporters & recent stats.

## Risk & Considerations
- Credential leakage prevention: never log tokens; mask in errors.
- Backpressure: if export queue grows, apply shedding (skip low severity / duplicate events).
- Observability: add latency histogram per integration (future) and error ratio gauges.

## Current Status Summary
All integrations: NOT IMPLEMENTED (logical placeholders only). Metrics + docs prepared for rapid addition.

---
Maintainer: AI-generated draft. Update as integration modules land.
