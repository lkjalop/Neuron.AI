# NEURONS API Contract (Validation Tier MVP)

Version: 0.1  
Scope: Endpoints required for Frontend MVP + new NLP + Gate Status + Ingestion Health.

---
## Conventions
- Authentication: `X-API-Key` header (predict/read surfaces) – lightweight until full auth layer.
- Pagination: `limit` + `offset` OR `page` + `page_size` depending on resource (legacy endpoints retained).
- Times: UNIX epoch seconds unless otherwise noted.
- All responses JSON with top-level object; lists wrapped as `{ items: [...], count: n }`.

---
## Endpoints Summary
| Path | Method | Purpose | Auth | Status |
|------|--------|---------|------|--------|
| `/health` | GET | Basic liveness | none | existing |
| `/vulnerabilities` | GET | Basic vuln list (legacy) | key (future) | existing |
| `/vuln/vulnerabilities` | GET | Enhanced vuln list | key | existing |
| `/vuln/findings` | GET | Paginated findings | key | existing |
| `/dashboard/latest` | GET | Latest dashboard snapshot | key | NEW |
| `/ingest/status` | GET | Connector ingest health | key | NEW |
| `/system/gate_status` | GET | Gate metrics & readiness | key | NEW |
| `/query/nlp` | POST | Translate natural language → IR + sample results | key | NEW |
| `/reports` | GET | List report runs (executive) | key | existing infra |
| `/reports/exec_summary` | POST | Generate executive summary report | key | existing |

---
## Schemas
### Dashboard Snapshot (`DashboardSnapshot`)
```jsonc
{
  "vulnerability_severity": {"CRITICAL": 12, "HIGH": 34, "MEDIUM": 80, "LOW": 120},
  "vulnerability_exploit_available": {"True": 20, "False": 226},
  "open_findings_severity": {"CRITICAL": 5, "HIGH": 12},
  "new_findings_7d": 40,
  "closed_findings_7d": 32,
  "generated_ts": 1736212345.123
}
```

### Ingestion Status (`IngestStatus`)
```jsonc
{
  "connectors": [
    {"name": "qualys_synth", "last_event_ts": 1736212000.1, "events_24h": 1200, "status": "OK"},
    {"name": "tenable_stub", "last_event_ts": null, "events_24h": 0, "status": "STALE"},
    {"name": "siem_synth", "last_event_ts": 1736212100.5, "events_24h": 540, "status": "OK"}
  ],
  "generated_ts": 1736212345.55
}
```

### Gate Status (`GateStatus`)
```jsonc
{
  "feature_snapshot_last_run": 1736212200.42,
  "variance_ok": true,
  "gating_report_version": "g1.0",
  "exposure_regression_ok": true,
  "anomaly_model_ready": false,
  "total_assets": 120,
  "total_vulnerabilities": 346,
  "scripts": {
    "data_variance": {"status": "ok", "stdev_min": 0.12},
    "exposure_regression": {"status": "ok"},
    "spike_injector": {"last_injected_ts": 1736211111.11},
    "gate_report": {"path": "artifacts/gate_report/latest.json"}
  },
  "generated_ts": 1736212345.90
}
```

### NLP Query Request
```jsonc
{ "query": "critical or high exploited older than 30 days top 20" }
```

### NLP Query Response (`NlpQueryResponse`)
```jsonc
{
  "ir": {
    "domain": "vulnerabilities",
    "clauses": [
      {"type": "severity", "operator": "in", "values": ["CRITICAL", "HIGH"]},
      {"type": "exploit_status", "operator": "equals", "value": true},
      {"type": "age", "operator": ">", "value": 30},
      {"type": "limit", "value": 20},
      {"type": "sort", "field": "severity", "direction": "desc"}
    ],
    "meta": {
      "confidence": 0.82,
      "fallback_used": false,
      "tokens": [
        {"raw": "critical", "normalized": "CRITICAL", "tag": "severity"},
        {"raw": "high", "normalized": "HIGH", "tag": "severity"},
        {"raw": "exploited", "normalized": "exploit_status", "tag": "exploit_status"},
        {"raw": ">30", "normalized": "30", "tag": "age_threshold"}
      ],
      "unparsed_tokens": []
    }
  },
  "preview": {"count": 20, "items": [/* vulnerability rows subset */]},
  "elapsed_ms": 42.3
}
```

### Error Shape
```jsonc
{ "error": "invalid_request", "detail": "Missing query field" }
```

---
## Endpoint Details
### GET /dashboard/latest
Returns most recent persisted snapshot; if none, computes fresh.
Response: `DashboardSnapshot`.

### GET /ingest/status
Calculates per-connector stats (best-effort; falls back to zeros). Response: `IngestStatus`.

### GET /system/gate_status
Aggregates gating artifacts from disk / memory; tolerant of missing files.

### POST /query/nlp
Body: `{ "query": str }`  
Returns: `NlpQueryResponse`.  
If confidence < 0.5 -> `ir.meta.fallback_used=true` and `preview` uses substring search.

---
## Change Log
- 0.1: Initial contract draft.

---
Prepared for implementation; actual schemas may include additional read-only fields (e.g., `source`).
