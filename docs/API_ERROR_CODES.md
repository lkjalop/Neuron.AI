# API Error Codes Catalog

Structured error envelope format:
```json
{
  "error": {"code": "<code>", "message": "<detail>"},
  "status": <http_status>,
  "correlation_id": "<id>"
}
```

| Code | HTTP | Meaning | Typical Causes | Notes |
|------|------|---------|----------------|-------|
| missing_pattern | 400 | Required pattern missing in hunt query | POST /hunt/query without pattern | Client input fix needed |
| missing_value | 400 | IOC value field absent | POST /ioc without value |  |
| invalid_event | 400 | Event validation failed (generic message prefix) | /ingest malformed payload | Prefixed in handler with context |
| unsupported_content_type | 400 | SBOM upload content type not JSON | Wrong Content-Type header |  |
| sbom_ingest_error | 500 | Unexpected SBOM synchronous ingest failure | Parser or processing bug | Examine logs |
| enqueue_failure | 500 | Failed to enqueue async SBOM job | Queue full/internal error | Retry may work |
| sbom_queue_full | 503 | Async SBOM job queue at capacity | High load or small queue size | Backoff & retry |
| predict_api_key_not_configured | 503 | Predict API key missing when required | Misconfig in env | Startup config check |
| write_api_key_not_configured | 503 | Write API key missing | Missing env |  |
| admin_api_key_not_configured | 503 | Admin API key missing | Missing env |  |
| persistence_unavailable | 503 | Vulnerability store not initialized | Not wired in test/dev | Transient in tests |
| list_unavailable | 503 | Failure listing findings (SLA/tickets) | DB outage/exception | Wraps original error |
| invalid_or_missing_api_key | 401 | API key absent or wrong | Auth header issue |  |
| deny_api_key | 401 | Key mismatch (metrics label) | Wrong key value | Exposed via metrics only |
| rate_limited | 429 | Token bucket throttle (returned body) | Exceeded RPS | Body plain string in metrics endpoint |
| job_not_found | 404 | Unknown SBOM job id | Wrong/expired id |  |
| replay_detected | 401 | HMAC replay attempt | Reused signature |  |

Additional dynamic codes may appear derived from exception class names in generic handler (lowercased). Keep this catalog updated when adding new explicit codes.
