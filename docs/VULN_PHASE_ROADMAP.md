# Vulnerability & Exposure Intelligence Roadmap (Phase 1 -> 4 Pivot Track)

Status: Draft (2025-09-04)
Scope: This document layers a 4-phase execution plan for the vulnerability scanning & exposure intelligence pivot (Amendment A14) while preserving compatibility with anomaly / neuromorphic detection roadmap.

---
## Guiding Principles
1. Dual-Track Harmony: Exposure intelligence features must enrich (not fork) anomaly fusion context (shared runtime params, metrics, audit).
2. Evidence Before Automation: Each escalation in actionability (risk scoring -> correlation -> SLA signaling -> guided response) requires quantitative validation & audit entry.
3. Deterministic First: Normalization, merging, and risk scoring must be reproducible (hashable advisory corpus, pure functions) before probabilistic enrichment (EPSS/ML risk uplifts).
4. Bounded Surface: Initial implementation avoids large dependency blast radius (keep to stdlib + existing infra) to accelerate iteration.
5. Audit-Centric: All weighting, enrichment, and SLA decisions are parameterized and logged through existing runtime param audit chain.

---
## Phase 1: Foundations & Data Integrity
Objective: Establish minimal ingestion + normalization + risk primitives producing stable, test-covered artifacts.
Deliverables:
- Schema (0003 migration): assets, sbom_components, asset_components, vulnerabilities, findings, finding_events.
- Normalizers: NVD (subset), OSV (subset), merge precedence (first CVSS wins).
- SBOM Parsing: CycloneDX component extraction (purl, version, ecosystem).
- Risk Engine (Deterministic Core): Weighted (cvss severity proxy, exploit placeholder, temporal decay, asset criticality).
- Runtime Params: `vuln.risk.weights.*`, exploit bonus cap, scan/enrichment intervals, SLA days (low/medium/high/critical).
- Metrics: scan cycles, normalization latency, active findings count, risk score gauge, finding state transitions.
- Agent: VulnerabilityScannerAgent (poll + recompute risk).
- Tests: normalization (NVD/OSV), merge logic, risk scoring (temporal decay & exploit bonus), SBOM parse.
Success Criteria:
- Test suite green; risk scoring stable across runs (variance <1e-9 diff for same inputs).
- Scan cycle < 1s with < 20 advisory docs (baseline synthetic).
- Risk score monotonic wrt severity & exploit flag; temporal decay reduces score for >180d age.
Out of Scope:
- Real feed pulling, EPSS/KEV enrichment, delta scans, correlation with anomalies.

## Phase 2: Enrichment & Correlation Scaffolding
Objective: Add external intelligence signals + finding lifecycle tracking while preparing correlation with runtime anomalies.
Deliverables:
- Enrichment Agent (skeleton) fetching: EPSS snapshot (batch), KEV catalog, exploit PoC flags.
- Advisory Chunk Hashing: Persisted normalized advisory blobs (advisory_chunks) with SHA256 for provenance.
- Risk Extensions: Additional factors (exploit probability via EPSS bucketization, KEV boost, anomaly_correlation placeholder factor default 0).
- Correlation Stub: Map anomalies to components/assets (heuristic field alignment) generating correlation ratio stored in finding_events.
- SLA Operationalization: Calculate days open vs SLA days param -> emits upcoming breach event when remaining < threshold (e.g., 20% SLA remaining).
- Metrics: enrichment cycles (status), correlation events, SLA breach countdown gauge, EPSS distribution summary (optional histogram).
- Tests: EPSS mapping, KEV flag effect on risk, SLA countdown edge cases, correlation heuristic (deterministic test fixtures).
Success Criteria:
- Enrichment cycle latency < 5s (synthetic stubs) and idempotent.
- Risk score increases with KEV/exploit > baseline; EPSS high bucket > medium > low.
- SLA breach events emitted precisely once per finding per breach window.
Out of Scope:
- ML-based exploit prediction, advanced graph correlation.

## Phase 3: Adaptive Exposure Prioritization & Fusion Linking
Objective: Link exposure risk dynamics directly into fusion reasoning & insights, introducing adaptive weighting and correlation-driven prioritization.
Deliverables:
- CorrelatorAgent: Maintains moving window of anomaly-to-finding co-occurrence -> correlation_factor (0..1) stored per finding.
- Risk Weight Adaptation: Optional adaptive tuning adjusting exploitability vs asset weight based on historical remediation velocity (governed; param bounds + cooldown).
- Insight Types: anomaly_correlated_vuln, approaching_sla_breach, rising_exploit_activity, stale_enrichment_data.
- Fusion Interface Hook: Expose top N high-risk correlated findings via insight context retrieval path.
- Metrics: correlation_factor gauge, adaptive_weight_adjustments_total, remediation_velocity histogram (days to closure), insight_generation_total{type}.
- Tests: correlation factor monotonic with co-occurrence count; adaptive tuner respects bounds & cooldown; insights gating thresholds.
Success Criteria:
- Correlated findings appear in >80% of anomaly contexts (synthetic mapping) when correlation_factor>0.5.
- Adaptive weight changes logged & never exceed bound; test asserts no oscillation (delta sign flips < threshold within window).
- Insight generation deterministic for fixed synthetic sequences.
Out of Scope:
- Direct modification of fusion anomaly decisions (advisory linking only in this phase).

## Phase 4: Proactive Guidance & SLA-Aware Orchestration
Objective: Provide guided response recommendations integrating risk, correlation, SLA, and anomaly trajectory—still human-in-loop.
Deliverables:
- Recommendation Engine: Ranks candidate actions (patch asset group, escalate exploit surge, extend SLA exception) with rationale & provenance hashes.
- Playbook DSL (Minimal): YAML or JSON describing action templates (patch_set, notify_channel, open_ticket) with variable interpolation.
- SLA Exception Workflow: Parameterized extension requests logged + hash chained.
- Metrics: recommendation_emitted_total{action_type}, playbook_execution_total{status}, sla_exceptions_total{status}.
- Tests: ranking determinism, playbook variable resolution, exception workflow audit integrity (hash chain continuity).
Success Criteria:
- Recommendation ranking stable across repeated runs with unchanged inputs.
- Hash chain for exceptions unbroken in test simulation (insertion order preservation).
- Latency: recommendation generation < 250ms for 100 candidate findings (synthetic).
Out of Scope:
- Automatic patch deployment, ticket system integration beyond stub, large-scale graph clustering.

---
## Cross-Phase Risk Controls
- Idempotent Agents: All agents must handle reentrancy; state transitions only once (use version or state checks).
- Bounded Memory: In-memory caches capped; eviction policy documented.
- Governance Logging: Every risk weight change -> audit log entry referencing amendment & justification.
- Determinism Tests: Core scoring & normalization verified via hash snapshot test (future addition) to detect accidental drift.

## Metrics Strategy Alignment
Vulnerability metrics intentionally mirror anomaly metric philosophy: explicit counters for lifecycle transitions, gauges for current intensity, histograms for latency. This symmetry enables unified executive dashboards and correlation-driven weighting experiments.

## Open Questions / Future Extensions
1. Multi-Tenancy Asset Overlap: Handling shared infrastructure components without data leakage.
2. Component Graph Depth: Deciding when transitive dependency explosion harms interpretability.
3. CVSS v4 Adoption Path: Migration plan once finalized (mapping table + dual-scoring period).
4. Exploit Probability ML: Whether to incorporate logistic model over EPSS + KEV + anomaly frequency.
5. Patch Saturation Curve: Modeling diminishing return of patching mid-severity vulns with no exploit signals.

## Exit Criteria for Pivot Validation
Pivot deemed successful when:
- Analyst alignment study: top 15 recommended findings match human triage priority >= 80%.
- Mean time to identify (MTTI) high severity (critical exploit-available) < 5 min after advisory ingestion (synthetic feed simulation).
- SLA breach prediction (warning events) accuracy > 90% (predicted vs actual breach occurrences on simulated timelines).

---
Generated as part of A14 execution; subsequent material changes require amendment + hash update.
