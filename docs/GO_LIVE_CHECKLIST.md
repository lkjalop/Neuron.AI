# Go-Live Checklist

This checklist covers configuration, health checks, and smoke tests required to take Neuron live with observability enabled.

## Required Environment Variables
Set these for the `app` service (container or process):

- `PREDICT_API_KEY`: API key used by clients for predict-scope endpoints (also protects observability proxies)
- `PROMETHEUS_URL`: Base URL for the upstream Prometheus server, e.g. `http://prometheus:9090`
- `GRAFANA_BASE_URL`: Base URL for the upstream Grafana, e.g. `http://grafana:3000`

Optional:
- `GRAFANA_TOKEN`: Bearer token for server-side rendered images via `/proxy/grafana/render`
- `ADMIN_API_KEY`: Admin scope for admin-only endpoints (metrics auth also accepts this)
- `ALLOW_CANONICAL_DOC_DRIFT=1`: Only for development; bypasses canonical doc hash guard
- `ALLOW_PARTIAL_READINESS=1`: Development-only; readiness returns `{"status":"degraded"}` even if Prometheus/Grafana envs are missing
- `STORY_MAX_CONTENT_BYTES`, `REPORT_MAX_CONTENT_BYTES`: Override size caps without changing runtime params

## Health Probes
- Liveness: `GET /health/live` (alias: `/healthz`)
- Readiness: `GET /health/ready` (alias: `/readyz`)
  - Returns `503` with a JSON body listing missing keys until `PREDICT_API_KEY`, `PROMETHEUS_URL`, and `GRAFANA_BASE_URL` are set.
  - When `ALLOW_PARTIAL_READINESS=1`, returns `200` with status `degraded` and the `missing` list for local dev without Prometheus/Grafana.

## Observability Smoke Tests (PowerShell)
Assumes the app is reachable at `http://localhost:8000` and you have the predict key in `$Env:API_KEY`.

```powershell
# 1) Liveness & readiness
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready

# 2) Metrics (requires key if configured)
curl -H "x-api-key: $Env:API_KEY" http://localhost:8000/metrics | Select-Object -First 20

# 3) Prometheus proxy (instant query)
$expr = "up"
curl -H "x-api-key: $Env:API_KEY" "http://localhost:8000/proxy/prom?q=$expr"

# 4) Grafana iframe URL (no token sent to browser)
curl -H "x-api-key: $Env:API_KEY" "http://localhost:8000/proxy/grafana/iframe?panelId=1&dashboard=neuron-kpis"

# 5) Grafana render (PNG) – requires `GRAFANA_TOKEN` on the server
curl -H "x-api-key: $Env:API_KEY" -o panel.png "http://localhost:8000/proxy/grafana/render?panelId=1&dashboard=neuron-kpis&width=800&height=400"
```

## Docker Compose
To bring up app + Prometheus + Grafana locally:

```powershell
docker compose -f docker-compose.observability.yml up --build
```

Then verify the smoke tests above. Tear down with:

```powershell
docker compose -f docker-compose.observability.yml down -v
```

## Notes
- Story and report size limits honor `STORY_MAX_CONTENT_BYTES` and `REPORT_MAX_CONTENT_BYTES` environment variables first. Tests rely on this precedence.
- `/metrics` requires a key when `PREDICT_API_KEY` or `ADMIN_API_KEY` is set; otherwise it throttles anonymously.
- For demos without keys, you can temporarily rely on ephemeral acceptance on predict/write scopes, but configure keys before production.
