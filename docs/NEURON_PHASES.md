# NEURON PLATFORM PHASES (Canonical Extraction)

Source: `Neuron-p1-5.txt` (extracted snapshot 2025-09-02)

> Immutable reference for Phase 1–5 scope. Implementation modules must not silently diverge; changes require audit entry.

This document captures the authoritative intent, scope, and high-level design elements for Phases 1 through 5 prior to code modularization. Each phase is frozen once copied; amendments require:
1. New section under "Amendments" with rationale
2. Audit log entry referencing commit hash
3. Updated manifest regeneration

## Table of Contents
1. Phase 1 – Data Ingestion & Normalization
2. Phase 2 – Baseline Detection & Metrics
3. Phase 3 – Spiking Neural Network (SNN) Prototype
4. Phase 4 – Predictive Fusion & Ensemble Reasoning
5. Phase 5 – Response Orchestration & Integrations
6. Amendments

---

## Phase 1 – Data Ingestion & Normalization
Canonical Goals:
- Capture low-level telemetry (initially simulated, future: eBPF) with minimal overhead.
- Normalize events into versioned `Event` schema (see src/core/event.py).
- Enforce multi-tenancy via `tenant_id` and isolation validation.
- Provide back-pressure & rate limiting strategy (token bucket placeholder).

Scope Elements (Original Doc References Pending):
- eBPF probe concept (C code extraction TODO)
- Async ingestion queue & batching
- Serialization format evaluation (JSON vs msgpack) – decision: start JSON, allow pluggable codec.

Non-Goals (Phase 1):
- Persistent datastore durability (in-memory acceptable)
- ML inference

## Phase 2 – Baseline Detection & Metrics
Canonical Goals:
- Implement simple statistical / heuristic detectors for anomalies per tenant.
- Emit metrics (Prometheus) for events, anomalies, latencies.
- Establish evaluation harness (synthetic data generation + scoring script).

Scope Elements:
- Rolling mean / std deviation anomaly flag
- Threshold configuration via performance tier
- Metrics: events_total, anomalies_total, processing_latency_seconds histogram

Non-Goals:
- Advanced ML / SNN integration
- Automated responses

## Phase 3 – Spiking Neural Network (SNN) Prototype
Canonical Goals:
- Integrate lightweight SNN model (snntorch) gated behind feature flag.
- Compare SNN output vs baseline detectors (A/B evaluation dataset).
- Memory & performance profiling harness.

Scope Elements:
- Simple feedforward or small recurrent SNN layer
- Input encoding strategy (rate or latency coding) for normalized events
- Evaluation metrics: precision, recall, F1, memory footprint MB, avg inference ms

Non-Goals:
- Large transformer embeddings
- Production rollout (experimental only)

## Phase 4 – Predictive Fusion & Ensemble Reasoning
Canonical Goals:
- Fuse signals from baseline + SNN + rule heuristics.
- Implement ensemble scoring & confidence calibration.
- Introduce reasoning agent (lightweight) to add contextual annotations.

Scope Elements:
- Weighted score aggregator with pluggable strategy
- Drift detection hooks for agent integrity (see IAM)
- Feature flag for enabling reasoning agent

Non-Goals:
- Autonomous decision execution
- Cross-tenant analytics (privacy backlog)

## Phase 5 – Response Orchestration & Integrations
## Amendments

### A14 – Vulnerability Scanning & Exposure Intelligence Pivot (Proposed)
Date: 2025-09-04
Rationale: Extend anomaly-centric platform with proactive software exposure reduction by integrating SBOM component intelligence, vulnerability ingestion (NVD/OSV/scanner outputs), enrichment (EPSS, KEV), and dynamic risk scoring correlated with runtime anomalies. This unlocks earlier customer value (traditional risk & patch prioritization) while preserving trajectory toward neuromorphic predictive fusion.

Scope Additions:
1. Schema: assets, sbom_components, asset_components, vulnerabilities, findings, finding_events, advisory_chunks.
2. Ingestion: CycloneDX/SPDX SBOM parser, NVD & OSV feed normalizers, optional Trivy/Grype adapter.
3. Enrichment: EPSS batch, KEV list, exploit availability flags, advisory chunk hashing.
4. Risk Scoring: Weighted multi-factor (cvss, exploit, exposure, age decay, churn, anomaly correlation, exploit bonus – control reductions) -> normalized risk 0..1 with SLA mapping.
5. Agents: VulnerabilityScannerAgent, VulnEnrichmentAgent (future), CorrelatorAgent (future), SLAWatcherAgent (future).
6. Insights: high_risk_unpatched, approaching_sla_breach, anomaly_correlated_vuln, active_exploit_detected.
7. Metrics: vuln_scans_total, vuln_scan_duration_seconds, vuln_findings_total{status}, vuln_risk_score_bucket, vuln_sla_breach_total, vuln_enrichment_requests_total{status}.
8. Governance: Runtime param weights auditable; advisory corpus hashed; amendment logged with hash chain.

Non-Goals (A14): Automated remediation execution, kernel-level exploit tracing, advanced exploit prediction, full vector store integration (deferred to later phase).

Success Indicators: >80% alignment of top 20 risk-ranked findings with analyst prioritization; anomaly correlation improves triage precision metrics; scan delta mode reduces full sync duration >40% after baseline.

Status: Proposed – implementation staged behind feature flag `vuln.scan.enabled`.
Canonical Goals:
- Provide response suggestion engine (human-in-loop) with cooldown + rollback safeguards.
- Integrate minimal external connectors (e.g., Slack webhook) behind explicit enable flags.
- Maintain exhaustive audit trail for every suggested action.

Scope Elements:
- Response playbook DSL (initial stub)
- Safety gates: dry-run, user approval, policy compliance check
- Integration abstraction layer

Non-Goals:
- Full automated remediation without approval
- Broad SaaS integration catalog (future backlog)

## Amendments

### A13 (Phase 4 Early Fusion & Temporal Intelligence Expansion) – Pending Hash
Date: 2025-09-03
Rationale: Introduce early Phase 4 fusion and temporal intelligence capabilities in a governed, observable manner before broad response orchestration. This batch establishes adaptive temporal contribution management, enriched policy context, and analyst-facing insight scaffolding to derisk future autonomous reasoning features.

Scope Additions (Phase 4 Preview Elements):
1. Adaptive Temporal Weight Tuner: Proportional uplift-driven adjustment of `fusion.weight.temporal` within governed bounds (min/max, cooldown, tolerance band). Emits cycle duration histogram + window size gauge + adjustment counters.
2. Precision Proxy Extension: Temporal detector integrated into false-positive proxy accounting with gating logic to suppress temporal contribution when proxy rate exceeds configured threshold.
3. Policy Context Provider: Runtime snapshot exporting calibrated quantile deltas (Δp90, Δp99) and temporal gating ratio for downstream policy / agent decisions.
4. Insights Engine Scaffold: Heuristic rule set generating structured insight objects (uplift deficit, calibration staleness, suppression elevation, quantile shift). No autonomous actions (advisory only) – prepares ground for future explainability & operator trust.
5. Temporal Model Evolution Stub: Deterministic multi-head TFT-style placeholder (`TFTMultiHeadStub`) enabling interface stabilization and testable shape/determinism prior to introducing learnable parameters.
6. Documentation: SOC temporal quick card (operational runbook) and agent workflow overview linking tuner signals to analyst narrative.

Non-Goals (A13): Production-grade transformer training, autonomous remediation, dynamic policy enforcement beyond advisory insights, external connector activation.

Success Indicators:
- Temporal weight converges within tolerance band around uplift target without oscillation (variance < configured tolerance after cooldown periods).
- Precision proxy rate does not degrade (> configured max) when temporal path active; gating ratio observable.
- Insights emitted with deterministic rule evaluations (unit tests confirm scenarios) – no false action triggers.

Metrics Added:
- `fusion_temporal_tuner_cycle_seconds` (histogram)
- `fusion_temporal_tuner_window_size` (gauge)
- `fusion_temporal_tuner_adjustments_total` / direction labels
- `precision_proxy_rate{detector="temporal"}` extension
- Gating ratio via policy context (exposed snapshot; may be promoted to metric if persistence/value proven)

Risks & Mitigations:
| Risk | Impact | Mitigation |
|------|--------|------------|
| Over-aggressive temporal scaling | Noise inflation | Bounded step size + max_abs_delta + cooldown enforcement |
| Quantile drift misinterpreted | Premature policy changes | Advisory-only insights; no automatic threshold mutation |
| Model interface churn later | Refactor tax | Stub stabilizes forward() contract early |

Exit / Graduation Criteria to Full Phase 4 Amendment:
1. Demonstrated uplift stability across ≥3 benchmark suites (noise + shift scenarios) with temporal active.
2. Insight accuracy review (manual analyst validation) – <5% misclassification rate in curated scenario set.
3. Policy context consumed by at least one downstream governance or UI component.

Audit Requirements:
 - Commit introducing A13 appended to `AUDIT_LOG.md` with artifact hashes.
 - `CANONICAL_DOC_HASH` updated post-merge.
 - Param changes for tuner initialization captured in `audit/param_changes.log`.

Status: Implemented (code + tests + docs). Pending hash update & potential graduation after benchmark validation.

---

### A12 (SNN Scaffold Integration & Observability) – Previously Recorded
Date: 2025-09-03
Rationale: (See Audit Entry A12) Establish neuromorphic prototype path with deterministic encoding & foundational metrics before adaptive fusion / temporal expansion.
Status: Closed – superseded by A13 for fusion evolution context; remains canonical for Phase 3 scope baseline.

### A11 (Phase 2.1 Reliability Scope Introduction) – Pending Implementation
Date: 2025-09-02
Rationale: After security hardening (A10) we identified a reliability gap: anomaly injection during load harness runs produced zero persisted anomalies due to queue drain timing + constant warm-up values generating zero variance. Before enabling any Phase 3 (SNN) experimental flag we must produce auditable anomaly evidence to justify baseline comparisons.

Scope Additions (Phase 2.1 – Reliability & Evidence):
1. Inline (synchronous) detection path for `/ingest` optionally enabled via header or flag to guarantee anomaly evaluation without relying solely on background queue timing.
2. Warm-up jitter injection in synthetic/load harness to avoid permanent zero-variance (std=0) windows that defer detection to MAD/abs-delta paths late or not at all.
3. Deterministic pipeline drain / flush mechanism (graceful shutdown or explicit flush endpoint) ensuring all queued events processed prior to export.
4. Persisted anomaly verification loop: run harness with anomaly injection -> flush -> export must yield non-zero anomalies; failure blocks Phase 3 gate.
5. Documentation cross-link to `PHASE1_2_SUMMARY.md` consolidating evidence and trade-offs; Learning Path updated with Phase 2.1 tasks.
6. Audit + hash update policy: canonical doc amendment recorded here; `CANONICAL_DOC_HASH` updated post-change; A11 entry added to `audit/AUDIT_LOG.md`.

Non-Goals (A11): Introducing SNN logic, altering statistical detector math, adding external persistence store.

Success Criteria: Dataset export after injected anomalies consistently reports anomaly_count > 0 across at least two consecutive runs; anomaly log JSONL contains varied reasons (e.g., std, abs_delta, hybrid_z/mad when hybrid enabled).

Security / Integrity Impact: No change to threat surface beyond additional endpoint or header gate; integrity guard remains enforced via updated hash.

Reference: See `PHASE1_2_SUMMARY.md` for narrative context and deviation log motivating this amendment.

---

## Phase Status & Backlog Summary (2025-09-03 Snapshot)

This section is a rolling (non-canonical) operational snapshot; it does NOT alter frozen canonical goals above. Items here may graduate into formal amendments or separate design docs after validation cycles.

### Recently Achieved (Since A11 Draft)
| Area | Achievement | Evidence |
|------|-------------|----------|
| Phase 3 SNN | RateEncoderV2 implemented (median+MAD scaling, burst gating, global shrink, density cap, min floor) | `docs/SNN_ENCODING.md` update, code in `src` (snn module) |
| Tuning | Uplift band (2.0–3.5× baseline) achieved with params (`rate_scale=1.03`, `global_shrink=0.4`, `min_floor=0.05`) | Benchmark runs via `scripts/set_params_and_run.py` (audit param log) |
| Guardrails | Encoder enumeration guard + density cap in place; param guard test added | `tests/test_runtime_param_guard.py` |
| Residual Path | Optional sequence residual booster integrated (disabled by default) | Code & doc section (SNN_ENCODING.md) |
| Documentation | Expanded encoding design with V2 + tuning guidelines | `docs/SNN_ENCODING.md` |

### Active In-Progress
| Item | Description | Next Action |
|------|-------------|-------------|
| Phase 2.1 Reliability (A11) | Flush & evidence harness enhancements | Implement queue flush + warm-up jitter code path |
| Phase Summary Automation | Hash + line mapping table population | Script to map sections to `Neuron-p1-5.txt` lines |

### Backlog (Proposed Priorities)
| Priority | Item | Rationale | Exit Criteria |
|----------|------|-----------|---------------|
| High | Residual-enabled benchmark evaluation | Determine net uplift vs noise with residual ON | Report comparing anomalies, density, false positive proxy |
| High | Periodic Shift Benchmark Variant | Provide predictable cyclical amplitude change to exercise residual forecasting path | New benchmark pattern adds sinusoidal + stepped shift; residual shows >0 mean positive contribution on shift phases |
| High | Precision Proxy Metric (Noise Window) | Quantify false positive tendency using designated low-signal pattern slice | Metric `snn.false_positive_proxy` emitted; residual run does not increase proxy >5% over control |
| High | Residual Enablement Gate | Prevent premature default activation | Gate: uplift_raw +5% min over 3 runs AND spike_energy delta <= +10% AND false_positive_proxy delta <= +5% |
| High | Training & Fine-tuning Benchmark Suite | Standardize repeatable sweeps (rate_scale, shrink, threshold) & capture uplift distribution variance | Benchmark script producing variance report + saved param sets |
| High | SOC Wiki / RAG Integration (Non-Technical Surface) | Provide analyst-friendly contextual retrieval for anomaly reason codes | RAG service returning top-k doc chunks for reason code & event context |
| Medium | Density Cap Regression Test (Added) | Prevent silent removal or mis-scaling of cap logic | Test failing if projected density not reduced when above cap |
| Medium | Auto-Calibration Loop (Threshold) Hardening | Smooth adaptive threshold to maintain target ratio | Converges within N intervals ± tolerance |
| Medium | Fusion Strategy Expansion | Introduce `baseline_priority`/`snn_priority` gating logic | Strategies selectable + unit tests |
| Low | Forecaster Model Upgrade | Replace stub with lightweight AR / EMA hybrid | Residual improves precision (measured) without >5% latency hit |
| Low | Sequence Persistence & Drift Metrics | Long-term distribution tracking | Drift alert triggers on synthetic shift scenario |
| Low | Compliance Mapping Automation | Generate control linkage table from doc annotations | Script output committed & hashed |

### Risk / Mitigation Snapshot
| Risk | Impact | Mitigation |
|------|--------|------------|
| Parameter drift post-tuning | Uplift out of band | Persist defaults + add periodic param hash check |
| Density cap disabled in prod | Spike storm & noise | Guard: disallow `debug_no_cap` unless ENV=dev |
| Residual over-amplifies noise | False positives | Keep residual disabled until benchmarked |
| Lack of variance in synthetic data | Misleading uplift | Add pattern diversity & noise injection module |

### Immediate Next (If Resumed)
1. Implement density cap regression test (now added below in test suite — see new test file).
2. Run residual-enabled benchmark & compare metrics.
3. Persist tuned defaults (`runtime_params.save_defaults()`) after locking.
4. Begin SOC wiki/RAG ingestion pipeline (doc chunker + vector store selection decision record).

---

### Residual Enablement Gate (Deferred)
The residual forecaster feature remains DISABLED by default. It may only be enabled by default once all criteria below are satisfied across at least 3 independent benchmark runs on the canonical synthetic suite and (when available) a labeled validation slice:

Gate Criteria (all must pass):
1. uplift_raw increase >= +5% versus control (residual disabled)
2. spike_energy increase <= +10%
3. false_positive_proxy increase <= +5%
4. No regression in density_cap enforcement (density stays within configured cap tolerance)
5. Audit entry recorded with benchmark hashes and param snapshot

Metrics Additions Required:
- `snn.false_positive_proxy` (counter or gauge) measured within designated noise window segments
- Optional: `snn.residual_contrib_mean` over run capturing average positive contribution magnitude

Failure Handling:
- If any single run violates (2) or (3) thresholds by >2x, residual experiments pause pending root cause analysis.

---

### Phase Transition Summary (Moving to Next Phase Planning)
Status (2025-09-03):
- SNN RateEncoderV2 stabilized with uplift in target band.
- Regression test coverage added for density cap and param guard.
- Residual path evaluated; remains off by default; gating criteria codified (see above).
- Backlog expanded with benchmark variant, precision proxy, and enablement gate.

Transition: Remaining residual enhancements and precision instrumentation are officially backlogged; focus shifts to early Phase 4 fusion strategy groundwork (introducing multiple fusion strategies and precision tracking) while maintaining SNN stability.

Next Phase Preparation Recommendations:
1. Introduce minimal fusion strategy interface & register existing pass-through as default.
2. Add precision proxy metric early so Phase 4 comparisons have baseline.
3. Begin RAG ingestion prototype concurrently (low coupling) to support analyst-context enrichment once fusion scoring emits reason metadata.

All above deferred tasks MUST NOT alter canonical sections without an amendment entry.

---

## Source Line Mapping (Pending Full Population)
| Phase Section | Original File | Approx Line Start | Approx Line End | Notes |
|---------------|---------------|-------------------|-----------------|-------|
| Phase 1 – Data Ingestion & Normalization | Neuron-p1-5.txt | TBA | TBA | To be filled after verification |
| Phase 2 – Baseline Detection & Metrics | Neuron-p1-5.txt | TBA | TBA |  |
| Phase 3 – Spiking Neural Network (SNN) Prototype | Neuron-p1-5.txt | TBA | TBA |  |
| Phase 4 – Predictive Fusion & Ensemble Reasoning | Neuron-p1-5.txt | TBA | TBA |  |
| Phase 5 – Response Orchestration & Integrations | Neuron-p1-5.txt | TBA | TBA |  |

Hash Policy: The SHA256 of this file is verified at application startup unless `ALLOW_CANONICAL_DOC_DRIFT=true` is set (dev only). Any modification requires an amendment entry + audit log update.

Placeholder: Full verbatim text extraction mapping line spans from original source is pending (next iteration). For now refer to original `Neuron-p1-5.txt` while modules are built. Once mapped, each section will gain a Source Line Mapping table.
