# Architecture, Services, and Deployment Overview

Date: 2025-09-10
Owner: Platform

## High-Level Diagram (textual)
- Browser (Analyst Console)
  - calls FastAPI backend
  - no direct Prometheus/Grafana tokens
- FastAPI Backend
  - Core APIs (dashboard, findings, tickets, feedback)
  - Proxies: `/proxy/prom`, `/proxy/grafana/*`
  - Scheduler & governance loops (where enabled)
- Observability
  - Prometheus (scrape `/metrics`)
  - Grafana (dashboards; render API)
- Persistence
  - Artifacts (JSON/JSONL)
  - Optional Postgres for dashboard cache

## Deployment Notes
- Set `ADMIN_API_KEY` and `PREDICT_API_KEY`.
- Set `PROMETHEUS_URL` and `GRAFANA_BASE_URL`.
- Optional: `GRAFANA_TOKEN` for server-side renders.

## Security Controls
- API keys required on predict/admin routes.
- Proxy inputs sanitized; variables allowlisted.
- Structured errors; rate-limits configurable.

## Runbook
- Health: `/healthz`, `/readyz` (if enabled), `/metrics`.
- Logs: `artifacts/` and audit chains.
- Backups: `artifacts/` tree and database (if used).
