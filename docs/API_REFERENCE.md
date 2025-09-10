# API Reference (Batch 1 Initial Export)

This document is generated in part by `docs/export_openapi.py` and augmented with human notes.

## Overview
Expose key operational and governance surfaces:
- `/governance/recommendations/recent` (NEW)
- `/diagnostics/config` (pagination + optional auth)
- `/fusion/decisions/recent`
- `/snn/status`
- `/metrics`

For the full machine-readable schema, run the export script:

```
python docs/export_openapi.py --out artifacts/openapi.json
```

## Authentication
Most administrative endpoints require header: `x-api-key: <ADMIN_API_KEY>`.
Some predictive & read-only surfaces may allow `PREDICT_API_KEY` fallback.
Diagnostics optional gate: supply `x-diagnostics-key` if `diagnostics.auth.required` param is true.

## Pagination Patterns
- Offset/limit: `/diagnostics/config`, `/governance/recommendations/recent`
- Tail-limit (newest first): `/fusion/decisions/recent`, `/ioc/hits/recent`
- Page/page_size style: `/findings/sla/upcoming`

## New Endpoint: Governance Recommendations
`GET /governance/recommendations/recent`
Query Params:
- `limit` (1..200)
- `offset` (>=0)
- `tenant` (optional tenant id filter)
- `action` (optional; `raise_threshold` or `lower_threshold`)
Response:
```
{
  "items": [
    {
      "ts": 1736292000.123,
      "tenant": "tenantA",
      "suggestion": {"action": "raise_threshold", "delta": 0.01, "reason": "shadow_fp_rate_diff", "diff": 0.0725}
    }
  ],
  "limit": 50,
  "offset": 0,
  "returned": 1,
  "total": 1,
  "more": false,
  "tenant_filter": "tenantA",
  "action_filter": null,
  "ts": 1736292001.004
}
```
Semantics: Non-mutating advisory derived from precision proxy differences; actions only applied if operators choose to adjust thresholds.

## Diagnostics Config
`GET /diagnostics/config?limit=100&offset=0&full=false`
Provides a slice of runtime params plus policy/exception summary. When `full=true`, entire map returned.

## Export Script Usage
```
python docs/export_openapi.py --out artifacts/openapi.json --markdown docs/API_REFERENCE.md
```
Will write JSON and optionally append basic counts to the markdown file.

## Rate Limiting
- Admin writes: enforced via token bucket (`ADMIN_RATELIMIT_RPS`).
- Predict reads: `PREDICT_RATELIMIT_RPS`.
- Metrics endpoint optionally rate limited if key presented.

## Error Format
```
{"error": {"code": "bad_request", "message": "details"}, "status": 400, "correlation_id": "<id>"}
```
Correlation id echoed via `x-correlation-id` header.

## Change Log (API Surface - incremental)
- v0.1.0: Added `/governance/recommendations/recent` (Batch 1)
```

<!-- OpenAPI Export Summary -->
Exported endpoints: 84; component schemas: 3.
