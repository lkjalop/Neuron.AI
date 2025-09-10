# NEURON Platform (Scaffold)

> Status: Hybrid Anomaly + Fusion Scaffold (2025-09-04). Core governance, fusion wiring, enrichment & insights demo active.

Developer environment guidance (Windows / PowerShell usage, testing shortcuts) is now documented in `DEVELOPMENT.md`.
Additional focused docs:
- Rule chaining: `docs/RULES_CHAINING.md`
- Retrieval ranking debug, memory linking & probes: see Retrieval & RAG Enhancements in `DEVELOPMENT.md`

## Central Dogma
See `docs/CENTRAL_DOGMA.md`. Human empowerment, transparency, reversibility.

## Directory Structure
```
src/                Source code modules
  config/          Performance tiers & settings
  core/            Core data contracts (Event)
  iam/             IAM (RBAC + ABAC + agent drift scaffolding)
  security/        (Future) encryption, integrity, supply chain
audit/              Audit log, manifest chain
docs/               Immutable & living documentation
scripts/            Utility scripts (manifest, future eval, synthetic data)
archives/           Release archives (zip + manifest snapshot)
```

## Getting Started
```
# (Optional) create virtual environment
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell

pip install -r requirements.txt

# Generate manifest (hash chain)
python scripts/generate_manifest.py

# (Optional) run security baseline
python scripts/security_baseline.py

# (Optional) export OpenAPI schema
python docs/export_openapi.py --out artifacts/openapi.json
```

## Domain Expansion (Batch 5)
New ingestion connectors and behavioral/network detectors extend coverage beyond generic events:

Connectors:
- `POST /ingest/edr` (process + user + optional dst)
- `POST /ingest/dns` (query, src_ip)
- `POST /ingest/netflow` (src_ip, dst_ip, bytes, protocol)
- `POST /ingest/siem` (generic normalized security events)

Detectors (heuristic initial pass):
- `lateral_movement`: distinct destination explosion per user.
- `persistence`: suspicious parent -> child (e.g. powershell.exe spawning reg.exe / schtasks.exe).
- `beaconing`: low-jitter periodic netflow intervals (avg <60s, low std).
- `dns_tunneling`: long high-entropy first DNS label.

Enrichment Chain (post-fusion):
- MITRE mapping (static seed) -> `mitre_techniques`.
- Threat intel stub -> `threat_intel.score` & tags (deterministic pseudo-score).

Artifact metadata exposed inside anomaly `metadata` field; see `docs/CONNECTORS_SPEC.md` for schema & examples.

Test coverage: `tests/test_behavioral_detectors.py` crafts synthetic events to ensure each detector and enrichment fires.

Runtime tuning of thresholds planned via future runtime params; current heuristics are code constants for clarity.


## Feature Flags (Environment Variables)

All flags are optional; defaults are safe & conservative.

| Env Var | Purpose | Default |
|---------|---------|---------|
| `NEURON_METRICS_ENABLED` | Expose Prometheus metrics | `true` |
| `NEURON_SNN_ENABLED` | Enable experimental SNN inference pipeline (Phase 3) | `false` |
| `ENABLE_SNN` | (Current orchestrator flag) Enable SNN detector | `false` |
| `EXPERIMENTAL_ISOFOREST` | Enable Isolation Forest detector | `false` |
| `ENABLE_FUSION` | Enable fusion layer (appends fused synthetic anomaly) | `false` |
| `FUSION_STRATEGY` | Fusion strategy name (`weighted_temporal`) | `weighted_temporal` |
| `SNN_DETERMINISTIC` | Deterministic spike encoding (paired with `SNN_SEED`) | `false` |
| `SNN_SEED` | Base seed for deterministic SNN encoding | `1337` |
| `NEURON_REASONING_AGENT_ENABLED` | Enable reasoning agent (Phase 4) | `false` |
| `NEURON_RESPONSE_AUTOMATION_ENABLED` | Allow response orchestration suggestions (Phase 5) | `false` |
| `NEURON_DEBUG` | Extra logging / debug behaviors | `false` |

### Runtime

Local run (development):

```powershell
pip install -r requirements.txt
python -m uvicorn core.main:app --reload --factory
```

Visit:
- http://localhost:8000/healthz
- http://localhost:8000/metrics (if enabled)
- http://localhost:8000/config/flags
- Diagnostics UI: http://localhost:8000/app/diagnostics.html (runtime params pagination, governance recommendations, normalization freshness chip)
- API Reference: see `docs/API_REFERENCE.md` (export machine schema: `python docs/export_openapi.py --out artifacts/openapi.json`)

### Additional Metrics (Hardening Batch 1)
### Detection Orchestrator Quick Start

Run baseline + Isolation Forest + SNN (deterministic) on synthetic stream:

```powershell
$Env:EXPERIMENTAL_ISOFOREST = "true"
$Env:ENABLE_SNN = "true"
$Env:SNN_DETERMINISTIC = "true"
$Env:SNN_SEED = "20250904"
python .\scripts\run_detection_pipeline.py --events 400 --tenant demo
```

Promotion gate evaluation:
```powershell
python .\scripts\evaluate_promotion.py
```

Compare detector configurations:
```powershell
python .\scripts\benchmark_compare_detectors.py --events 600
```

Replay existing dataset (JSONL events):
```powershell
python .\scripts\replay_events.py --input .\events.jsonl --summary artifacts\perf\replay_summary.json
```

Reliability (baseline only):
```powershell
python .\scripts\run_reliability_check.py
```

Reliability (with fusion enabled):
```powershell
$Env:RELIABILITY_ENABLE_FUSION = "true"
$Env:RELIABILITY_FUSION_MULTIPLIER = "1.5"
python .\scripts\run_reliability_check.py
```
Failure if:
1. Baseline relative variance > tolerance (default 0.15)
2. Fused relative variance > tolerance
3. Fused relative variance > baseline_rel * multiplier

Print detector status (ordered, with fusion weights if enabled):
```powershell
python .\scripts\print_detector_status.py
```

Insights + policy enrichment demo:
```powershell
python .\scripts\demo_insights_policy.py --events 200 --tenant demo
```

Precision proxy interpretation:
- False positives in noise windows increment `neuron_precision_proxy_false_positive_total`.
- Noise window count increments `neuron_precision_proxy_windows_total`.
- Derived rate per detector exposed in `neuron_precision_proxy_rate` gauge.

Deterministic SNN rationale: ensures repeated runs over same event stream produce identical spike trains (given stable feature values) for reproducible benchmarking and gating.

Fusion Layer:
- Enabled via `ENABLE_FUSION=true` (strategy selectable with `FUSION_STRATEGY`)
- Current strategy: weighted temporal sum with per-detector weights (`fusion.weight.<detector>` persisted in param store)
- Adaptive tuner script (`scripts/run_tuner.py`) adjusts weights based on detector unique contribution ratio (precision proxy penalty forthcoming)
- Metrics: `neuron_fusion_anomalies_total`, `neuron_fusion_score`, `neuron_fusion_contributor_weight`, `neuron_fusion_active`

Flush Helper:
- Centralized `flush_all()` consolidates detector flush timing; invoked at orchestrator flush.

Reliability Fusion Stability:
- Script now evaluates baseline vs fused anomaly relative variance.
- Guardrails ensure fusion doesn't introduce disproportionate instability.

Upcoming (planned):
- Precision proxy false-positive penalty integrated into tuner adjustments
- Knowledge ingestion (CVE/MITRE/OWASP) & ontology mapping
- Temporal transformer integration feeding fusion weights

New counters / gauges:
- `neuron_events_dropped_total{tenant,reason}`
- `neuron_ingest_errors_total{error_type}`
- `neuron_normalizer_redactions_total{reason}`
- `neuron_fusion_anomalies_total{tenant,strategy}`
- `neuron_fusion_active{strategy}`
- `neuron_detector_unique_ratio{tenant,detector}`

### Canonical Document Integrity Guard
- Canonical: `docs/NEURON_PHASES.md`
- Stored hash: `audit/CANONICAL_DOC_HASH`
- On mismatch: startup raises unless `ALLOW_CANONICAL_DOC_DRIFT=true` (dev only).


## Tier Configuration
Simple Python module in `src/config/performance.py`. Active tier set by env `NEURONS_TIER`.

## Event Schema & Validation
`src/core/event.py` provides `Event` dataclass and `validate_event`.

## IAM (RBAC + ABAC + Drift)
`src/iam/authz.py` includes:
- Role definitions
- Attribute policies (tenant isolation, agent risk gating)

### Case Lifecycle (Phase 4 Enhancements)

The platform supports an in-memory Case abstraction grouping related anomalies and findings.

Behaviors:
* Auto-Merge: New case within `case.auto_merge.window_seconds` (default 300s) of an existing same-tenant case merges into the older case.
* SLA Overdue: Cases exceeding `case.sla.seconds` (default 3600s) flagged with `stats.overdue`; aggregate exposed via `neuron_case_overdue_total`.
* Promotion: Single-shot promotion when a case accumulates >=3 network anomalies OR >=2 open findings, incrementing `neuron_case_promotions_total` and adding a timeline `promotion` event.
* Confidence Evolution: `_update_case_confidence(case_id, confidence)` records timestamped confidence points (max 200 retained) and updates `last_confidence` used for anomaly export enrichment.
* Timeline Filtering: `GET /cases/{id}/timeline?type=<event_type>` filters by event type.

Key Endpoints:
* `POST /cases/from_anomaly/{anomaly_id}` – create/fetch w/ auto-merge semantics.
* `GET /cases/{id}/summary` – stats including overdue flag, promotion state, confidence evolution.
* `GET /cases/{id}/timeline` – chronological events (reverse order) with optional type filter.

Metrics:
* `neuron_case_total` (Counter)
* `neuron_case_timeline_events_total` (Counter)
* `neuron_case_promotions_total` (Counter)
* `neuron_case_overdue_total` (Gauge)

Runtime Params:
* `case.auto_merge.window_seconds`
* `case.sla.seconds`
* `fusion.memory.uplift.threshold` (gates memory multiplier on temporal weight)
* `fusion.memory.signal.seed` (seed default for `fusion.weight.memory_signal`)

Loader Persistence:
Cases now append to `artifacts/dataset/cases.jsonl`. To hydrate on startup ensure `_load_cases_persisted()` is invoked (hook can be added in a future persistence phase or manually at the end of FastAPI startup event).

Rotation Strategy:
The case persistence file auto-rotates when either threshold is exceeded:
* Size: `CASE_PERSIST_MAX_BYTES` (default 5MB)
* Lines: `CASE_PERSIST_MAX_LINES` (default 20000)
Rotation produces suffix files: `cases.jsonl.1` (most recent prior), `cases.jsonl.2` (older). Only current file is appended. Rotation is best-effort and silent on errors.

Memory Artifact Ingestion:
Endpoint: `POST /memory/artifact`
Body fields:
```json
{ "artifact_id": "mem123", "case_id": "<optional>", "anomaly_id": "<optional>", "confidence_delta": 0.05 }
```
Resolution order: explicit `case_id` > map `anomaly_id` via existing case root index. On success increments memory artifact count, appends timeline event, persists case, and optionally bumps confidence evolution by `confidence_delta`.
Returns: `{ "status": "ok", "case_id": "...", "artifact_id": "..." }`

Memory Weight Seeding & Uplift Gating:
Runtime params:
* `fusion.memory.signal.seed` – initial seed applied to `fusion.weight.memory_signal` if unset (bounded ≤1.0).
* `fusion.memory.uplift.threshold` – minimum `FUSION_MEMORY_VERIFIED_RATIO` required before memory multiplier `(1 + w_mem)` amplifies temporal weight.
If ratio below threshold, multiplier remains 1.0 ensuring stability until confirmations accumulate.

New Endpoints:
* `GET /cases/search` – filters `tenant`, `promoted`, `overdue` with pagination.
* `GET /executive/kpis` now includes case roll-up stats.

Exporter Enrichment:
Anomaly records emitted by the baseline detector now include `case_id` and `case_confidence` when available, enabling downstream correlation without extra lookups.

Persistence Note: Current implementation is in-memory (Phase 4). Future phases will introduce durable storage and indexing for cross-process continuity.
- Drift monitor placeholder

### Phase 5 (Response Scaffold)

Adds a deterministic, dry‑run response recommendation layer with governance‑guarded automated escalation.

Key capabilities:
1. Recommendation Engine (`GET /response/recommendations/{case_id}`) – ranks potential actions (ticket escalation, asset quarantine, memory acquisition request) using weighted factors (confidence, overdue age, promotion state). Weights & thresholds are runtime tunable.
2. Playbook Preview (`POST /response/playbook/preview/{case_id}`) – returns a stable deterministic plan (synthetic hashed action IDs) for UI preview; always dry‑run (no side effects) while `response.playbook.dry_run_only` is true.
3. Automated Escalation (`POST /response/automation/run_once` + background loop) – periodically evaluates open cases and records escalation decisions (ticket/quarantine preference) only when governance composite and policy thresholds are satisfied. Executions are still logical decisions (no external system side‑effects yet) for safe iteration.
4. Memory Artifact Catalog (`POST /memory/artifact/catalog`) – structured ingestion path emitting catalog metrics and persisting JSONL lines to `artifacts/memory/catalog.jsonl` for retrieval & recommendation context.
5. Governance Guardrails – automation requires governance composite to be within `[response.auto.escalate.gov_low, response.auto.escalate.gov_high]`, preventing actions during unstable high‑risk or unhealthy low‑signal periods.

Runtime parameters (selected):
- `response.recommend.enable` – master toggle for recommendation & preview endpoints.
- `response.playbook.dry_run_only` – keep actions non‑executing (true by default).
- `response.weight.confidence|overdue_age|promotion` – scoring weight vector.
- `response.quarantine.min_confidence`, `response.ticket.min_confidence` – action eligibility thresholds.
- `response.memory.min_artifacts_for_skip` – skip acquisition recommendation once enough artifacts captured.
- `response.auto.escalate.enabled` – enable background & manual automation evaluation.
- `response.auto.escalate.min_confidence`, `response.auto.escalate.min_overdue_s` – policy gates.
- `response.auto.escalate.require_promoted` – restrict to promoted cases only.
- `response.auto.escalate.gov_low`, `response.auto.escalate.gov_high` – governance composite guard band.
- `response.auto.escalate.max_per_hour` – safety rate limiter.

Metrics (Prometheus):
- `response_recommendations_total{outcome}` – recommendation endpoint success/error counts.
- `response_playbook_previews_total{outcome}` – playbook preview counts.
- `response_automation_decisions_total{result}` – recorded automation decisions by selected action.
- `response_automation_last_ts` – unix timestamp gauge of last automation pass making a decision.
- `response_action_score` – histogram of action scores (observability of scoring distribution).
- `memory_artifact_catalog_total{result}` – catalog ingestion outcomes.
- `memory_artifact_catalog_size` – gauge of catalog line count.

Background Loop:
Started during startup; every `agents.loop.interval_s` seconds it invokes a lightweight evaluation that appends decisions to an in‑memory ring buffer surfaced at `/response/automation/history` (default max 200 entries). Hourly rate limiting enforced before scanning cases.

Determinism & Audit:
Scores derived from fixed formula and runtime param snapshot; tie‑breakers sort by action name for stable ordering. Parameter changes are fully audited (`audit/param_changes.log` with hash chain) so historical decision rationale can be reconstructed given case state snapshots.

Planned Next (post scaffold):
- Optional execution path (when `response.playbook.dry_run_only=false`) with external ticketing / EDR integration shims.
- Expanded action taxonomy (notification, enrichment, containment variants).
- Governance-based dampening / cool‑off tracking per action type.
- UI surfacing of rationale components & composite contributions.

#### Phase 5 Execution Enhancements (Action Execution Path)

The scaffold now includes a guarded execution endpoint enabling selective transition from dry‑run recommendations to tracked action executions.

Endpoint:
- `POST /response/execute/{case_id}` body: `{ "action": "<action_name>", "dry_run": <bool default false> }`
  * Honors `response.execution.enable` (global kill‑switch)
  * Enforces per‑action cooldown (`response.action.cooldown_s`) and per‑case hourly cap (`response.action.max_per_case_per_hour`)
  * When `dry_run` true no stateful execution recorded (metrics still observe attempt outcome)
  * Returns structured result: `{ "case_id":..., "action":..., "executed": bool, "reason": <skip_reason?> }`

Runtime Params (new):
- `response.execution.enable` – enable real execution attempts (default false keeps system in observe mode)
- `response.action.cooldown_s` – minimum seconds between identical action executions for a given case (default 60)
- `response.action.max_per_case_per_hour` – safety upper bound of executions per case per rolling hour (default 5)

Metrics (new):
- `neuron_response_action_executions_total{action,outcome}` – outcome: `executed` | `dry_run` | `rejected`
- `neuron_response_action_cooldown_skips_total{reason}` – reasons: `cooldown`, `hour_cap`, `disabled`

Rationale Enrichment: Recommendation objects now embed `components.weights` exposing `w_conf|w_overdue|w_promotion` plus raw feature factors for UI explanation and future what‑if analysis.

#### Phase 6 Executive Dashboard (Initial Cache & KPIs)

Adds lightweight executive KPI aggregation with cache to reduce recomputation overhead for frequent refresh clients.

Endpoint:
- `GET /executive/dashboard` – returns summary fields (case counts, overdue, governance composite, automation activity, vulnerability snapshot, anomaly volume buckets). Response shape stable & additive.

Caching:
- In‑memory snapshot cached for `executive.dashboard.cache_ttl_s` seconds. Hit/miss instrumented.

Runtime Param (new):
- `executive.dashboard.cache_ttl_s` – cache TTL seconds (default 15)

Metrics (new):
- `neuron_executive_dashboard_cache_total{outcome}` – `hit` | `miss`

Operational Notes:
- All execution & dashboard metrics follow existing Prometheus naming conventions (snake_case + unit suffix when timing/size semantics apply)
- Duplicate metric definition guard: consolidated single definitions in `core/metrics.py` (avoid CollectorRegistry collision during test imports)

Example (enable execution then run an action):
```powershell
# Enable execution
curl -X POST http://localhost:8000/admin/params/update -H "x-api-key: <KEY>" -H "Content-Type: application/json" `
  -d '{"key":"response.execution.enable","value":true,"reason":"enable lab execution"}'
# Attempt action (dry_run=false)
curl -X POST http://localhost:8000/response/execute/<case_id> -H "x-api-key: <KEY>" -H "Content-Type: application/json" `
  -d '{"action":"escalate_ticket","dry_run":false}'
```

Telemetry Interpretation:
- Spike in `neuron_response_action_cooldown_skips_total{reason="cooldown"}` indicates operators requesting faster iteration; consider lowering cooldown or batching actions.
- Sustained `rejected` outcomes under executions counter may indicate governance policy mismatches or disabled flag toggling.

## Compliance Tracking
See `docs/COMPLIANCE_TRACK.md`. Update via audit log.

## Roadmap Extraction
Phase 1–5 canonical content will be migrated from `Neuron-p1-5.txt` into structured modules. Future/experimental sections will be isolated in `docs/FUTURE_CAPABILITIES.md`.

### Forward Reference (Phase 6 & Beyond)
Preparatory documentation and design scaffolds for upcoming phases:
| Area | Doc | Purpose |
|------|-----|---------|
| Executive Dashboard | `docs/PHASE6_DASHBOARD.md` | KPI catalog, endpoints, personas |
| Failsafes & Health States | `docs/FAILSAFE_DESIGN.md` | Degradation matrix, state machine |
| Branding & Tokens | `docs/BRANDING.md` | Visual & verbal consistency |
| Handbook | `docs/HANDBOOK.md` | Stakeholder overview & RAG-ready structure |
| Learning Path Deep Dive | `docs/LEARNING_PATH.md` | Extended training & quiz |
| Gate Report Generator | `scripts/generate_gate_report.py` | Evidence bundle assembly |
| Security Scan | `scripts/security_scan.ps1` | Static & dependency scan summary |

These forward-looking assets are additive; they do not alter Phase 1–2 canonical scope but reduce friction for Phase 3+ initiation.

## Contribution Rules
1. Never modify `docs/CENTRAL_DOGMA.md` directly; append an audit entry proposing changes.
2. Every substantive change -> regenerate manifest.
3. Add rationale block to `audit/AUDIT_LOG.md` referencing advisory ID.

## Security & Shift-Left (Planned)
- Pre-commit: ruff, bandit, detect-secrets, formatting.
- SBOM + vulnerability scan (trivy or grype).
- Image signing (future) with cosign.

## Vulnerability Scanner & SBOM Quickstart (Preview)

Enable scanner loop (environment flag) and ingest a minimal SBOM to get vulnerability + finding views.

### 1. Enable Scanner
```powershell
$Env:VULN_SCAN_ENABLED = "1"
```
Optionally shorten interval (default placeholder: 3600s):
```powershell
curl -X POST http://localhost:8000/admin/params/update -H "x-api-key: <KEY>" -H "Content-Type: application/json" -d '{"key":"vuln.scan.interval_seconds","value":600,"reason":"lab faster"}'
```

### 2. Ingest SBOM
```powershell
curl -X POST http://localhost:8000/vuln/ingest_sbom -H "x-api-key: <KEY>" -H "Content-Type: application/json" -d '{
  "asset_name": "checkout-service",
  "document": {"components": [
    {"name": "openssl", "version": "3.0.13", "purl": "pkg:openssl/openssl@3.0.13", "type": "library"}
  ]},
  "asset_metadata": {"criticality": 0.9}
}'
```

### 3. List Vulnerabilities
```powershell
curl -H "x-api-key: <KEY>" "http://localhost:8000/vuln/vulnerabilities?severity=HIGH"
```

### 4. View Findings
```powershell
curl -H "x-api-key: <KEY>" http://localhost:8000/vuln/findings
```

See `docs/VULN_OVERVIEW.md` for analyst-focused explanation and architecture.

## Observability (Batch 3 Enhancements)

New latency, file state and runtime parameter metrics plus correlation ID middleware were added to improve debugging and performance analysis.

### Correlation ID
Every HTTP response now includes header `x-correlation-id` (16 hex chars). Clients may supply their own header; otherwise a value is generated. Include this ID in logs or support tickets to trace request paths.

### Endpoint Latency Histograms
Histograms use native Prometheus `_bucket` convention (default buckets). Label dimensions intentionally small to prevent cardinality explosion.

- `story_endpoint_latency_seconds{endpoint, outcome}` endpoints: `create|fetch|prune` outcomes: `success|not_found|expired|error`
- `report_endpoint_latency_seconds{endpoint, outcome}` endpoints: `commit|diff_apply|versions|version_get|integrity_scan` outcomes: `success|not_found|error|mismatch|clean`

Example PromQL (p95 story create latency last 10m):
```
histogram_quantile(0.95, sum(rate(story_endpoint_latency_seconds_bucket{endpoint="create"}[10m])) by (le))
```

### File State Gauges
Reflect current persistence file sizes and last maintenance operation times (unix epoch seconds):

- `story_file_size_bytes`
- `report_file_size_bytes`
- `story_last_prune_ts`
- `report_last_integrity_scan_ts`

Example: alert if story file grows >10MB:
```
story_file_size_bytes > 10 * 1024 * 1024
```

### Runtime Parameter Export
Selected tunable values emitted as gauges (allowlist only):
`runtime_param_value{key="story.max_content_bytes"}` and similar for:
`story.ttl_seconds`, `report.max_content_bytes`, `eli5.cache.max_entries`, `eli5.cache.ttl_seconds`.

Example: change-rate monitoring of story size limit (increase >20% in 6h):
```
(
  max_over_time(runtime_param_value{key="story.max_content_bytes"}[6h]) -
  min_over_time(runtime_param_value{key="story.max_content_bytes"}[6h])
) / min_over_time(runtime_param_value{key="story.max_content_bytes"}[6h]) > 0.2
```

### Maintenance Counters (Previously Added)
- `story_prune_total{compacted}` (Counter) – number of story records pruned; `compacted="true"` indicates a compaction pass occurred.
- `report_integrity_total{outcome}` – outcomes: `clean|mismatch|error` from integrity scans.
- `story_file_rotations_total` / `report_file_rotations_total` – file rotation counts.

### Sample Dashboard Panels
1. Story/Report Latency (p50/p95): use `histogram_quantile` over respective histograms.
2. Integrity Scan Health: `sum(increase(report_integrity_total{outcome="mismatch"}[24h]))`.
3. File Growth Trend: `increase(story_file_size_bytes[1h])`.
4. Param Drift: graph `runtime_param_value` series.

### Testing
`tests/test_observability_metrics.py` asserts presence of the new metric families to prevent accidental regression during refactors.

### Extension Points
Correlation ID is stored at `request.state.correlation_id` for future structured logging or distributed tracing stubs.

### Prometheus Alerting Examples (SOC Friendly)
Add the following to a Prometheus rules file (YAML). These focus on actionable, low-noise signals a non-technical SOC analyst can understand quickly.

```
groups:
  - name: neuron-core
    rules:
      # 1. Report Integrity Mismatch Spike
      - alert: NeuronReportIntegrityMismatchSpike
        expr: increase(neuron_report_integrity_total{outcome="mismatch"}[15m]) > 0
        for: 5m
        labels:
          severity: medium
        annotations:
          summary: "Report integrity mismatch detected"
          description: >-
            A stored report version failed integrity verification in the last 15 minutes.
            Action: Investigate recent report changes or file system integrity.

      # 2. Story Prune Inactivity (possible stuck cleanup)
      - alert: NeuronStoryPruneStale
        expr: (time() - neuron_story_last_prune_ts) > 3600
        for: 10m
        labels:
          severity: low
        annotations:
          summary: "Story prune has not run in over 1h"
          description: >-
            Story cleanup may be stalled. If file size also growing investigate I/O or lock contention.

      # 3. High Story Create Latency (p95 > 250ms over 10m)
      - alert: NeuronStoryCreateLatencyHigh
        expr: histogram_quantile(0.95, sum(rate(neuron_story_endpoint_latency_seconds_bucket{endpoint="create"}[10m])) by (le)) > 0.25
        for: 10m
        labels:
          severity: medium
        annotations:
          summary: "Story create latency elevated (p95 > 250ms)"
          description: >-
            User-facing story operations are slow. Check disk saturation or CPU contention.

      # 4. Integrity Scan Missing (no scan in 6h)
      - alert: NeuronReportIntegrityScanStale
        expr: (time() - neuron_report_last_integrity_scan_ts) > 21600
        for: 15m
        labels:
          severity: low
        annotations:
          summary: "No report integrity scan in >6h"
          description: >-
            Schedule or trigger an integrity scan to maintain assurance.

      # 5. Rapid Param Drift (story size limit changed >20% within 6h)
      - alert: NeuronRuntimeParamDriftStorySize
        expr: (
          max_over_time(neuron_runtime_param_value{key="story.max_content_bytes"}[6h]) -
          min_over_time(neuron_runtime_param_value{key="story.max_content_bytes"}[6h])
        ) / clamp_min(min_over_time(neuron_runtime_param_value{key="story.max_content_bytes"}[6h]), 1) > 0.2
        for: 30m
        labels:
          severity: low
        annotations:
          summary: "Story size limit changed >20% in 6h"
          description: >-
            Review audit log for justification; unexpected changes can affect storage and performance.
```

Operator Tips (Plain Language):
- Integrity mismatch = stored file tampered or write interrupted. First step: re-run scan, then diff recent filesystem changes.
- Prune stale = cleanup job quiet; verify process running and disk not full.
- High latency = user wait complaints soon; check host load (CPU, disk) and recent deployments.
- Param drift = confirm authorized change (see `audit/param_changes.log`).

### Quick Start: Run App + Prometheus + Grafana

Spin up the full observability stack locally (app on :8000, Prometheus :9090, Grafana :3000):

```powershell
docker compose -f docker-compose.observability.yml up --build
```

Then visit:
- App health: http://localhost:8000/healthz
- Metrics raw: http://localhost:8000/metrics
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin / admin)

Dashboard auto-loads under folder `Neuron` (title: "Neuron Observability").

Tear down:
```powershell
docker compose -f docker-compose.observability.yml down -v
```

To enable tracing later (if OTLP collector added): set `NEURON_OTEL_ENABLED=1` for the `app` service.



## License
(TBD – choose before public distribution.)

## Phase 1 & 2 (IOC / Hunting / SLA / Ticketing) Additions

### Phase 1 Optional Enhancements (Extended Hardening & Ergonomics)

This batch layers lifecycle management, caching, deduplication, validation, adaptive capacity and standardized error telemetry onto the initial Phase 1 hunting + IOC feature set. All functionality is in‑memory (stateless across restarts) but fully audited via the runtime parameter hash chain.

Key Objectives:
1. Reduce noise (IOC hit de‑duplication window)
2. Control memory growth (IOC TTL + max retained)
3. Improve hunt performance (query result caching)
4. Provide safe pre‑ingest validation (`/ingest/validate`)
5. Enforce per‑tenant fairness (rate limiting)
6. Illuminate failures (structured error codes + metric)
7. Dynamically allocate hunt buffer share (adaptive high‑activity tiering)

#### New / Updated Endpoints
| Endpoint | Method | Auth | Purpose | Notes |
|----------|--------|------|---------|-------|
| `/ingest/validate` | POST | none (demo) | Dry‑run normalization & field validation (no state mutation) | Returns `{"valid": bool, "errors": [...]}` and increments `neuron_ingest_validate_total{outcome}` |
| `/ioc/revoke/{ioc_id}` | POST | admin | Revoke (logical delete) an IOC immediately | Prunes from active set; counts towards expiry metrics if TTL also triggered |

`/ingest` now applies per‑tenant rate limiting when `ingest.rate.per_tenant_per_min > 0` (429 with standardized error envelope `rate_limited`).

#### Standardized Error Envelope & Codes
All error responses follow:
```json
{"error":{"code":"<short_code>","message":"<detail>"},"status":<http_code>,"correlation_id":"..."}
```
Metric: `neuron_error_code_total{code}` increments for observability (e.g. `validation_failed`, `rate_limited`, `not_found`, `unauthorized`).

#### Runtime Parameters (New in Optional Batch)
| Key | Purpose | Default | Bounds / Notes |
|-----|---------|---------|----------------|
| `ioc.ttl.seconds` | Expire IOC records older than TTL (0 disables) | `0` | 0..31,536,000 |
| `ioc.max_retained` | Max IOC entries kept (oldest pruned) | `10000` | 100..1,000,000 |
| `ioc.hit.dedupe_window_s` | Suppress duplicate IOC hits within window | `0` | 0..86,400 |
| `hunt.query.cache.size` | LRU cache capacity for hunt queries (pattern+field) | `0` | 0..10,000 |
| `hunt.query.cache.ttl_s` | TTL seconds for cached hunt results | `120` | Active only if size>0 |
| `ingest.validation.enable` | Enable `/ingest/validate` | `true` | Toggle without code redeploy |
| `ingest.rate.per_tenant_per_min` | Rate limit ingest by tenant (0 disables) | `0` | 0..1,000,000 |
| `ingest.rate.burst_capacity` | Initial burst capacity for rate limiting | `10` | 1..1000 |
| `ingest.normalizer.redaction` | Fields redacted from normalized output | `["user.id","process.args"]` | JSON array of field names |
| `ioc.expiry_check.interval_s` | Interval for SLA breach scanning | `30` | 10..3600 |
| `ticket.sla.seconds` | Default ticket SLA (used for breach detection) | `3600` | 300..86400 |

#### Phase 2 Enhancements (Extended Detection & Response)

This batch introduces initial ticketing integration, expanded detector coverage, and response scaffolding.

Key Features:
- Ticketing: create, update, link, search
- Detection: AWS CloudTrail, Azure audit logs, GCP logs
- Response: initial recommendation engine + playbook preview

New Endpoints:
- Ticketing: `POST /tickets`, `GET /tickets/{id}`, `PATCH /tickets/{id}`, `GET /tickets?status=&case_id=`, `POST /tickets/{ticket_id}/link_case/{case_id}`
- Detection: `POST /ingest/cloudtrail`, `POST /ingest/azure`, `POST /ingest/gcp`
- Response: `GET /response/recommendations/{case_id}`, `POST /response/playbook/preview/{case_id}`

New Runtime Params:
- `ticket.sla.seconds` (default 3600) – used to compute `sla_due_ts` and drive breach detection

Background:
- SLA scan loop (30s interval) marks tickets as breached once overdue (except `closed`).

Metrics:
- `neuron_tickets_total{status}` – active tickets by status
- `neuron_ticket_transitions_total{from_status,to_status}` – lifecycle transitions
- `neuron_ticket_sla_breach_total{severity}` – first-time SLA breaches

Planned Next (6.2+): provider abstraction (execution hooks), SLA time-to-ack histograms, feedback loop integration.
