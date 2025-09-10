# Decisions Checklist (Frontend/Backend Integration)

Date: 2025-09-10
Owner: Platform
Status: Finalized

## Grafana Embed Strategy
- [x] In-app exploration uses Grafana iframes via backend proxy `GET /proxy/grafana/iframe`.
- [x] Report exports use server-side rendered PNGs via `GET /proxy/grafana/render`.
- [x] No Grafana tokens in browser; backend injects `Authorization: Bearer ...` when configured.
- [x] Input sanitization for dashboard/panel/vars; allowlist variables; prevent control characters.

## Prometheus Metrics Access
- [x] All PromQL goes through backend proxy `GET /proxy/prom` (instant or range).
- [x] API requires Predict/Admin key; basic expression sanitization.
- [x] Time range bounded server-side; non-200 from Prometheus mapped to HTTP error.

## Editable Report Behavior
- [x] Snapshot-by-default embeds; per-embed Live toggle optional.
- [x] New Findings popup: non-blocking toast with [Preview Diff][Update][Keep].
- [x] Provenance ribbon on embeds: dataset/time/filters/query hash.
- [x] Export forces snapshot unless explicitly allowed.

## Tuner Approvals & Audit
- [x] Roles: SOC Lead / Platform Admin approve; analysts preview only.
- [x] Time-bounded change windows with auto-revert and manual rollback.
- [x] Immutable audit entries; notify on out-of-band changes.

## API/Auth Contracts
- [x] Predict/Admin API keys accepted on predict routes.
- [x] Unset keys → 503; invalid/missing → 401; structured error payloads.

## Frontend → Backend Mapping
- [x] Dashboard: `GET /dashboard/latest` (predict)
- [x] Insights: `GET /insights`
- [x] Findings SLA: `GET /findings/sla/upcoming` (predict)
- [x] Tickets: `POST /tickets/remediation` (predict)
- [x] Feedback: `POST /feedback` (flag-gated)
- [x] Metrics: `GET /proxy/prom`
- [x] Grafana: `GET /proxy/grafana/iframe`, `GET /proxy/grafana/render`
