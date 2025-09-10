# Neuron Platform Architecture & Readiness (Phase Summary)

## 1. High-Level System Flow
Event (ingest) -> Feature Extraction / Detectors (Baseline, SNN Proto, Temporal Residual, Isolation Forest optional) -> Fusion Arbitrator (strategy configurable) -> Anomaly Buffer + (batched) Persistence -> Retrieval / Enrichment (RAG-lite) -> Agent Layer (Planner + future specialized agents) -> Insights / Dashboards / Admin APIs.

```
   +-----------+        +------------------+        +-----------------+        +----------------------+
   |  Ingest   |  --->  |  Detectors       |  --->  | Fusion Arbitrator| --->  | Anomaly Sink & TTL   |
   | (FastAPI) |        |  (Baseline/SNN/  |        | (weighted_sum /  |       | (Postgres batched)   |
   |           |        |   Temporal/iForest)       |  pass_through...) |       +---------+----------+
   +-----------+        +------------------+        +---------+-------+                 |
                                                                   |                   v
                                                               +---v----+       +-------------+
                                                               | Agents |<----->| Message Bus |
                                                               +---+----+       +------+------+ 
                                                                   |                   |
                                                                   v                   v
                                                          +-----------------+   +-------------+
                                                          | Retrieval/RAG   |   | Insights /  |
                                                          | (keyword/hybrid)|   | Dashboards  |
                                                          +-----------------+   +-------------+
```

## 2. Core Components
### 2.1 Ingestion Layer
- `POST /ingest` supports optional inline detection (header gated) for low-latency anomaly decisions.
- Backpressure: queue; drops counted via metric `EVENTS_DROPPED_TOTAL`.
- Admin endpoints provide governed runtime param updates (with audit hashing) and anomaly retrieval.

### 2.2 Detectors
- Baseline: rolling mean, stddev / MAD hybrid (warmup, jitter governance).
- SNN (proto): lightweight accumulator or (future) LIF mode. Currently single layer (limitation: no deep spiking network yet).
- Temporal residual model: optional variance / simple attention scaffold. Provides residual variance-derived anomaly contribution and adaptive temporal weight tuner.
- Isolation Forest (optional): retrains on cadence; integrates as weighted signal when enabled.

### 2.3 Fusion Arbitrator
Strategies: `pass_through`, `baseline_priority`, `consensus_only`, `weighted_sum`.
- `weighted_sum` combines: baseline indicator, SNN normalized activity, temporal residual signal, optional iForest, and transformer deviation (scaffold) when `fusion.weight.transformer > 0`.
- New metrics: `neuron_fusion_transformer_weight`, `neuron_fusion_transformer_deviation` expose configured weight & last deviation.
- Precision proxy metrics (SNN unique vs union) tracked for early quality signals.

### 2.4 Adaptive Temporal Weight Tuner
- Observes uplift ratio (temporal anomalies / baseline) vs target.
- Adjusts `detection.temporal.weight` within bounded step / absolute caps, respecting cooldown and min baselines.
- Audited via runtime parameter change log.

### 2.5 Persistence Layer
- Structured migrations (`storage/migrations.py`) create: `anomalies`, `calibration_quantiles`, `schema_migrations`.
- Batched anomaly persistence (`storage/anomaly_sink.py`): queue + interval flush, per-row `INSERT ... ON CONFLICT DO NOTHING` with TTL pruning (default 7 days) executed opportunistically.
- Calibration quantiles persisted via upsert in calibrator save path.
- Idempotent migration test ensures safety on repeated startups.

### 2.6 Retrieval & Enrichment
- Lightweight RAG: keyword or hybrid scoring (embedding component behind abstraction). Dummy embedding default; OpenAI provider optional (cost guarded via env flag & key presence). Cap on retained chunks.
- Enrichment gating based on severity for insight context.

### 2.7 Agent Layer & Message Bus
- `AgentRegistry` with in-process pub/sub (`publish` / `subscribe`).
- Planner Agent publishes heartbeat (1 Hz max) to `heartbeat` topic including temporal enable flag & uptime.
- Future agents: response orchestrator, threat summarizer, remediation recommender, guardrail validator.

### 2.8 Governance & Audit
- Runtime params in `_SCHEMA` with type + bounds; updates audited to `audit/param_changes.log` + hash chain head for tamper detection.
- Canonical document integrity check (`NEURON_PHASES.md` hashed) at startup; block or warn depending on override flag.

### 2.9 Metrics & Observability
- Prometheus style metrics via `core.metrics` (not fully enumerated here): ingestion counters, processing latency, anomaly counts, suppression alerts, param changes, guard trips.
- Executive aggregator composes rolling window KPIs for dashboard consumption (suppression rate, overlap ratios, anomaly volumes).

## 3. External Integration Surface (Future Roadmap Alignment)
| Domain | Current State | Planned Evolution |
|--------|---------------|-------------------|
| Firewall / IDS / IPS logs | Manual ingest JSON normalization (user responsibility) | Schema adapters + protocol parsers; eBPF for kernel events |
| SIEM / SOAR | Pull-style anomalies API | Push/webhook + STIX export + playbook triggers |
| Embeddings | Dummy + OpenAI provider | Local transformer, vector DB integration (qdrant stub wiring) |
| Automated Response | None | Guarded action agents (isolate host, block hash) with approval workflow |
| Streaming Bus | In-process queue | External (Kafka / NATS) adapter with backpressure management |
| Deep Temporal Models | Variance / simple attention scaffold | TFT / Transformer encoder + learned gating |
| Spiking Network Depth | Single-layer proto | Multi-layer recurrent / conv SNN with calibration tooling |

## 4. Readiness & Limitations
### Production-Ready Strengths (Phase Scope)
- Deterministic baseline detector with guardrails.
- Config governance + auditable param changes.
- Batched persistence with TTL & idempotent migrations.
- Modular fusion supporting incremental enhancement.
- Heartbeat + message bus enabling operational monitoring.

### Current Limitations / Gaps
1. No LLM reasoning integration (agents are rule/scaffold only).
2. Predictive modeling limited (no sequence forecasting beyond simple residual variance; `seq.forecaster.enable` is scaffold).
3. Spiking architecture shallow (single layer; no advanced synaptic dynamics or learning rules yet).
4. No kernel-level telemetry (eBPF probes absent).
5. No automated containment / response actions (detection only).
6. Minimal resilience on DB failure (sink drops silently; future: retry with exponential backoff + DLQ).
7. No multi-tenant auth segmentation beyond rudimentary tenant filter.
8. Retrieval lacks persistence (memory-only index; restart clears context).
9. No horizontal scaling orchestration (single-process model; no sharding / partition of detector state).
10. Lack of structured alert severity taxonomy beyond basic score-based gating.
11. No RBAC / multi-role admin model (single API key + optional HMAC).
12. Limited test coverage for failure injection (e.g., simulating partial writes, queue saturation under stress).

### Risk Mitigations Implemented
- Parameter bounds prevent extreme disabling misconfigs.
- Hash chain logging for parameter tamper detection.
- `CREATE TABLE IF NOT EXISTS` & idempotent migrations reduce deploy fragility.
- Heartbeat for liveness at agent layer (future: escalate if missing). 

## 5. Suggested Next Enhancements (Prioritized)
1. Reliability: add retry & circuit breaker to anomaly sink persistence; metrics for queue depth & flush failures.
2. Observability: `/agents/heartbeats` endpoint streaming recent heartbeat payloads; expose sink stats.
3. Security: RBAC roles, per-tenant auth tokens, envelope signing for ingestion.
4. Temporal Modeling: Implement true transformer temporal encoder + residual gating; begin evaluation harness.
5. SNN Evolution: Multi-layer LIF with learnable thresholds & dropout-style sparsity controls.
6. Retrieval Persistence: Pluggable vector store (Qdrant / pgvector) with migration-managed schema.
7. Automated Response: Action agent with simulation mode + approval gating.
8. Streaming Integration: Kafka ingestion adapter + offset checkpointing.
9. Adaptive Cost Control: Budget guard for external embedding calls (throttle or downgrade based on spend).
10. Forensics: Trace store persistence + query APIs for historical anomaly context windows.

## 6. Success Criteria Snapshot
| Capability | Current | Target (Next Phase) |
|------------|--------|---------------------|
| Mean ingest -> anomaly decision latency | Low ms (inline path) | Maintain <50ms p95 under load |
| Anomaly persistence durability | Best-effort (no retry) | At-least-once with retry + metrics |
| Temporal uplift tuner stability | Manual spot checks | Quantified via evaluation harness & rollback guard |
| Parameter audit integrity | Hash chain only | Remote attestation + tamper alarm |
| Agent extensibility | Basic registry & pub/sub | Dynamic loading + sandbox isolation |

## 7. Data Model (Current)
- `anomalies(id, tenant, detector, score, fusion_score, event_time, payload JSONB)`
  - Indexes: `event_time`, `tenant`.
- `calibration_quantiles(tenant PK, p50, p90, p99, updated)`
- `schema_migrations(id PK, applied_at)`

## 8. Operational Playbook (Lite)
- Startup: migrations -> pipeline -> anomaly sink -> planner agent.
- Heartbeat Monitoring: subscribe to `heartbeat` topic; trigger alert if stale > N seconds.
- Param Change: use `/admin/params/update` with audit reason; verify log hash chain.
- Incident Triage: pull `/anomalies?tenant=...`; correlate with retrieval context & residual metrics.

## 9. Conclusion
The platform has reached a structured foundation: governed configuration, modular detection/fusion, emerging temporal adaptation, and operational scaffolds (heartbeat + migrations + batched persistence). Key investments next phase should harden durability, deepen modeling (temporal + SNN), and open controlled automation channels (response + richer agents) while expanding observability and multi-tenant security.

### 2.10 Batch 18 Observability Hardening (New)

New components introduced in Batch 18 to deepen runtime introspection and reliability:

| Component | Path | Purpose |
|----------|------|---------|
| Tracing spans | `observability/tracing.py` | Lightweight nested span timing for ingestion → fusion → governance/report cycles. |
| Governor instrumentation | `governance/weight_governor.py` | `governor.evaluate` span per tenant weight evaluation, shadow mode simulation. |
| Report tracing & diff audit | `reports/unified_pipeline.py` + `core/fusion_weight_audit.py` | `report.bundle`, `report.render_html`, `report.diff` spans and hashed `REPORT_DIFF` audit entries. |
| Watchdog | `observability/watchdog.py` | Monitors backlog metric; applies temporary detection weight back-off & gradual restore. |
| Reliability recorder | `observability/reliability.py` | Failure event ring buffer + `reliability_playbook.json` artifact (counts, avg durations, sample errors). |
| Shadow mode | `governance/weight_governor.py` (param: `governance.shadow_mode`) | Logs proposed adjustments without mutating runtime params. |

Operational Effects:
* Faster RCA via span chains (governor latency, report generation breakdown).
* Controlled adaptation under load: watchdog prevents runaway anomaly backlog amplification.
* Integrity continuity: report diff hashed into audit log for provenance.
* Safer tuning experiments: shadow mode validates adjustment heuristics before activation.

Runtime Params Added (Representative):
* `watchdog.enable`, `watchdog.backlog.threshold`, `watchdog.backoff.factor`, `watchdog.restore.after_s`, `watchdog.interval_s`.
* `governance.shadow_mode` (0/1 toggle).

Artifact Outputs:
* `artifacts/reliability_playbook.json` – rolling window failure aggregation.
* `audit/AUDIT_LOG.md` – new `REPORT_DIFF` lines with diff hash & key counts.

Future Extension Hooks:
* OTLP exporter for spans.
* Backlog metric formalization (replace placeholder gauge with ingestion queue depth).
* Automated SLO breach alerts tying into policy engine (planned Batch 19+).

### 2.11 Batch 19 Policy & Compliance Automation (New)

Purpose: Convert detection coverage + runtime parameter governance into enforceable, attestable posture controls.

Components:
| Component | Path | Purpose |
|-----------|------|---------|
| Policy DSL Loader | `policy/dsl.py` | Load & normalize JSON/YAML policy documents (versioned). |
| Compliance Scoring | `policy/compliance.py` | Compute composite score (coverage, requirements, adjustment adherence, stability). |
| Exception Registry | `core/main.py` (in-memory) | Temporary exception overlay with expiration times. |
| Attestation Snapshot | `artifacts/policy_snapshot.json` | Signed (HMAC) snapshot of latest score & components. |
| API Endpoints | `/policy/apply`, `/policy/list`, `/policy/score/{id}`, `/policy/exception` | Operate policy lifecycle & retrieve scores/exceptions. |

Score Composition (initial heuristic):
`score = 0.4*coverage + 0.3*requirements + 0.2*adjustments + 0.1*stability`

Key Policy Fields:
* `allowed_adjust_range`: Map param -> [min,max] authoritative bounds.
* `min_coverage_by_class`: Required fractional coverage per tactic/class.
* `required_techniques`: Must be covered unless exempted.
* `exceptions`: Items with `expires` epoch timestamp removed from compliance pressure.

Attestation:
* Snapshot contains score object + HMAC SHA256 signature (env `POLICY_SIGNING_SECRET`).

Extensibility Roadmap:
* Multi-policy layering & precedence.
* Exception approval workflow with audit chain linkage.
* Coverage weight by asset criticality (Batch 21 exposure graph integration).
* Policy violation alerting integrated into executive KPI flags.



---
*Generated: automated architecture snapshot (Phase status as of current commit).*