# External Data Source Connectors (Placeholders)

This document defines how synthetic data used today can be *safely and cleanly replaced* with real telemetry from SIEM, SOAR, firewalls, IDS/IPS, cloud provider logs, or observability platforms (Datadog, AWS CloudWatch, Azure Monitor, etc.).

## Goals
1. Maintain determinism & auditability (hashable manifests) even when moving to live feeds.
2. Enforce governance: no uncontrolled data fields (PII/Secrets) enter the detection pipeline.
3. Provide a *narrow ingestion contract* decoupled from vendor specifics.

## Connector Design Principles
- **Pull → Normalize → Validate → Emit**: Each connector pulls raw records, maps them to the internal `Event` structure, validates, and only then emits.
- **Schema Stability**: Preserve `features`, `raw`, `labels` (optional in real-time), `meta.source` enrichment.
- **Low Coupling**: Vendor-specific auth/config isolated in dedicated submodule (e.g., `src/core/ingest/connectors/splunk.py`).
- **Backpressure & Rate Limits**: Use shared rate limiter; connectors MUST respect `ratelimit.*` runtime params.
- **Integrity & Replay Defense**: Optionally include original record hash in `meta.original_hash` for uniqueness/replay detection.

## Event Mapping Template
```jsonc
{
  "tenant_id": "<derived or static>",
  "timestamp": 1735949200.123,
  "event_type": "network.flow" | "auth.login" | "proc.exec" | ...,
  "raw": { /* minimally transformed vendor payload subset */ },
  "features": { /* numeric features only (already scaled or raw) */ },
  "labels": { /* optional; present only in supervised backfill */ },
  "meta": {
    "source": {
      "type": "siem.splunk" | "siem.sentinel" | "observability.datadog" | "cloud.aws.cloudwatch" | "ids.suricata" | "firewall.paloalto",
      "ingest_connector_version": "0.1.0",
      "vendor_account": "<id>",
      "original_hash": "<sha256(raw vendor record)>",
      "synthetic": false
    }
  }
}
```

## Data Source Categories & Notes
| Category | Examples | Key Feature Extraction Ideas |
|----------|----------|------------------------------|
| SIEM | Splunk, Sentinel, QRadar | Counts, rarity scores, response codes, src/dst cardinality |
| SOAR | Cortex XSOAR, Swimlane | Playbook execution latency, action frequency |
| IDS/IPS | Suricata, Zeek, Snort | Alert severity encoding, signature rarity, byte/packet rates |
| Firewalls | Palo Alto, Fortinet | Deny/allow ratios, session duration stats |
| Observability | Datadog, New Relic | Error rate deltas, latency P95 shift, saturation metrics |
| Cloud Provider | AWS CloudWatch, Azure Monitor | API call anomaly, IAM action dispersion, resource metric spikes |

## Placeholder Modules (Planned)
```
src/core/ingest/connectors/
  __init__.py
  splunk.py        # search API / export; pagination → async fetch → normalize
  sentinel.py      # log analytics queries
  cloudwatch.py    # filter log events & metrics
  datadog.py       # timeseries + logs API
  suricata.py      # eve.json tail / streaming
```

## Security & Compliance Controls
- **Secret Management**: All credentials retrieved via `security.secrets.get_secret()`; never inline in code.
- **Field Allowlist**: Predefine acceptable `raw` keys per connector; reject & count violations.
- **PII Scrub Hook**: Optional transformer chain executed before `dict_to_event`.
- **Audit Log**: Each connector start/stop + error bursts appended to `audit/AUDIT_LOG.md` (future automated hook).
- **Hash Manifest**: For batch ingestions, produce dataset manifest analogous to synthetic generator (`schema: external.dataset.v1`).

## Transition Strategy from Synthetic → Real
1. Maintain synthetic + real dual-mode behind feature flag `ingest.enable_external`.
2. Side-by-side evaluation harness (extend `evaluate_snn.py`) to compare anomaly yield vs synthetic baseline.
3. Resource Guard: temporarily cap external ingestion rate to protect latency budgets.
4. Progressive Expansion: start with one category (e.g., CloudWatch metrics) then layer in others.

## Open Questions / Future Work
- Automatic schema inference with rejection list? (Risk: drift & silent field creep.)
- Feature store abstraction vs inline feature extraction.
- Cross-tenant isolation in multi-tenant SIEM streams.

## How to Contribute a Connector (Checklist)
1. Add `<name>.py` in `connectors/` implementing `fetch(batch_size) -> List[Event]`.
2. Implement environment variable or secret-based config retrieval.
3. Map raw vendor fields → numeric features (document mapping in module docstring).
4. Add unit tests using redacted sample payloads (no live credentials).
5. Update this doc + audit log with connector introduction.

---
This document is a living placeholder until real integrations commence. Keep additions minimal, auditable, and consistent with governance docs.
