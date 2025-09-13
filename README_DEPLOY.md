# Deploying NEURON (AWS / Azure / GCP)

This guide outlines environment variables, container build/run steps, and cloud-specific notes for a minimal production deployment.

## Image build and run (local/dev)

- Build: `make image` (production multi-stage)
- Run (dev server): `make run`

Expose the following environment variables in your runtime:

- `PREDICT_API_KEY`: required for predict-scope endpoints (and Grafana/Prom proxy auth)
- `ADMIN_API_KEY`: optional; used for admin endpoints and also allowed for predict scope
- `PROMETHEUS_URL`: e.g., `http://prometheus:9090`
- `GRAFANA_BASE_URL`: e.g., `https://grafana.example.com`
- Optional:
  - `GRAFANA_TOKEN`: Bearer token for image rendering endpoints
  - `ALLOW_PARTIAL_READINESS=1`: allows degraded readiness in dev
  - `DATABASE_URL`: Postgres connection string

## AWS (ECS/EKS)

- Secrets: store keys in AWS Secrets Manager or SSM Parameter Store (e.g., `/neuron/PREDICT_API_KEY`). Inject into task definitions or pods.
- Load balancer: expose service with ALB/NLB; forward HTTP(S) to the container (port 8000) or to an Ingress (for EKS).
- Prom/Grafana:
  - Managed Prometheus (AMP) or self-hosted Prometheus; set `PROMETHEUS_URL`.
  - Grafana: hosted (Grafana Cloud) or self-managed on EC2/EKS; set `GRAFANA_BASE_URL` and optional `GRAFANA_TOKEN`.
- Postgres: Amazon RDS; set `DATABASE_URL`.

## Azure (AKS/App Service)

- Secrets: store in Azure Key Vault; inject via managed identity or App Service settings.
- Ingress: Application Gateway or NGINX Ingress for AKS; TLS termination at gateway.
- Prom/Grafana:
  - Azure Monitor managed Prometheus (Mimir-compatible endpoints) or self-hosted; set `PROMETHEUS_URL`.
  - Grafana: Azure Managed Grafana or self-hosted; set `GRAFANA_BASE_URL` and optional `GRAFANA_TOKEN`.
- Postgres: Azure Database for PostgreSQL; set `DATABASE_URL`.

## GCP (GKE/Cloud Run)

- Secrets: store in Secret Manager; mount via Secret Manager CSI driver (GKE) or inject as env (Cloud Run).
- Ingress: Cloud Load Balancing for GKE; Cloud Run managed HTTPS.
- Prom/Grafana:
  - Managed Prometheus (Cloud Monitoring collector/Prom lens) or self-hosted; set `PROMETHEUS_URL`.
  - Grafana: self-managed or Grafana Cloud; set `GRAFANA_BASE_URL` and optional `GRAFANA_TOKEN`.
- Postgres: Cloud SQL; use the SQL Proxy or Private IP; set `DATABASE_URL`.

## Health checks and readiness

- Liveness: `GET /health/live` returns 200 with version/uptime.
- Readiness: `GET /health/ready` requires envs `PREDICT_API_KEY`, `PROMETHEUS_URL`, `GRAFANA_BASE_URL` (503 if missing). Dev mode: set `ALLOW_PARTIAL_READINESS=1` to return 200 with status `degraded`.

## Observability and rate limiting

- `/metrics` is protected by API key when configured; if no key configured, anonymous access is throttled.
- Per-scope token buckets: adjust via `PREDICT_RATELIMIT_RPS/BURST`, `ADMIN_RATELIMIT_RPS/BURST`, etc.
- Optional OTEL tracing: set `NEURON_OTEL_ENABLED=1` and configure exporters.

## Example: Kubernetes Deployment snippet

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: neuron
spec:
  replicas: 2
  selector:
    matchLabels: { app: neuron }
  template:
    metadata:
      labels: { app: neuron }
    spec:
      containers:
        - name: app
          image: your-registry/neuron-ai:latest
          ports:
            - containerPort: 8000
          env:
            - name: PREDICT_API_KEY
              valueFrom: { secretKeyRef: { name: neuron-secrets, key: PREDICT_API_KEY } }
            - name: ADMIN_API_KEY
              valueFrom: { secretKeyRef: { name: neuron-secrets, key: ADMIN_API_KEY } }
            - name: PROMETHEUS_URL
              value: "http://prometheus:9090"
            - name: GRAFANA_BASE_URL
              value: "https://grafana.example.com"
          livenessProbe:
            httpGet: { path: /health/live, port: 8000 }
            initialDelaySeconds: 10
          readinessProbe:
            httpGet: { path: /health/ready, port: 8000 }
            initialDelaySeconds: 10
```

## Example: Docker run (single host)

```powershell
$env:PREDICT_API_KEY="predictkey"
$env:PROMETHEUS_URL="http://localhost:9090"
$env:GRAFANA_BASE_URL="http://localhost:3000"
$env:ALLOW_PARTIAL_READINESS="1"
docker run --rm -p 8000:8000 -e PREDICT_API_KEY -e PROMETHEUS_URL -e GRAFANA_BASE_URL -e ALLOW_PARTIAL_READINESS neuron-ai:prod
```

## Troubleshooting
- 401 on `/metrics`: provide `X-API-Key` header.
- 429 on `/metrics`: scrape too frequent; adjust `PREDICT_RATELIMIT_*`.
- Graphs banner shows error: set `GRAFANA_BASE_URL` and ensure connectivity.
- Readiness not ready (503): set missing envs or enable partial readiness for dev.
