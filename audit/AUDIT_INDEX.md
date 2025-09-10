# Audit Entries Index (A01–A08)

Purpose: Rapid retrieval of governance & performance milestones for RAG / wiki queries. Each entry links evidence artifacts & rationale for future phases (e.g., SNN integration, compliance review, incident forensics).

| ID  | Date        | Title / Phase Focus                            | Core Themes                                   | Key Artifacts (hash in gate report if applicable) | Retrieval Tags |
|-----|-------------|-------------------------------------------------|-----------------------------------------------|---------------------------------------------------|----------------|
| A01 | 2025-09-02  | Initial Scaffolding                            | Canonical dogma, repo skeleton, audit start    | docs/CENTRAL_DOGMA.md                             | scaffolding,canonical,governance |
| A02 | 2025-09-02  | Batch 1 Hardening                              | Metrics, rate limiting, integrity guard, tests | docs/NEURON_PHASES.md, metrics, ratelimit, tests  | observability,hardening,integrity |
| A03 | 2025-09-02  | Runtime Params & Secrets Scaffold              | Governed tuning, secret stub, adaptive threshold | runtime_params.py, secrets.py, baseline.py        | tuning,params,secrets |
| A08 | 2025-09-02  | Phase 2 Baseline Gate Closure                  | Evaluation evidence, threshold sweep, performance, dataset export, integrity hashes | baseline_metrics.json, threshold_sweep.json, load_metrics.json, dataset manifest, gate_report | baseline,threshold,performance,gating |
| A12 | 2025-09-03  | SNN Scaffold & Observability Integration       | Neuromorphic scaffold, metrics, introspection, resource guard placeholder | snn.py, metrics.py, main.py, SNN_ENCODING.md, test_snn_detector.py | snn,experimental,observability,governance |

(IDs A04–A07 intentionally reserved / skipped in this prototype timeline for focus; future expansion can backfill or renumber with alias mapping.)

## Entry Summaries

### A01 – Initial Scaffolding
Establishes immutable central dogma and begins append-only audit trail; foundation for all integrity checks.

### A02 – Batch 1 Hardening
Introduces tenant isolation tests, rate limiter, expanded metrics; reduces unknowns before scaling feature complexity.

### A03 – Runtime Parameters & Secrets
Enables auditable, bounded tuning (range validation) and lays groundwork for secure secret management prior to SNN complexity.

### A08 – Phase 2 Baseline Gate Closure
Locks measured statistical baseline (precision 1.0 / recall ~0.116 at threshold 2.0) with reproducible artifacts & hashes; forms regression benchmark before neuromorphic uplift.

### A12 – SNN Scaffold & Observability Integration
Introduces gated experimental SNN detector with deterministic encoding and new metrics (latency, spike density, activity) plus /detectors endpoint; establishes measurement foundation prior to advanced spiking model & adaptive threshold experiments.

## RAG / Query Examples
- "What was the locked baseline threshold?" -> A08.applied_value (2.0)
- "Show baseline F1 at Phase 2 gate" -> A08 KeyMetrics (0.208)
- "List metrics added during first hardening" -> A02 description & referenced metrics module
- "How are parameter changes audited?" -> runtime_params.update_param (A03) + param_changes.log tail (A08 gate report)

## Forward Links
- Upcoming: IAM enforcement & RBAC (post A08)
- Neuromorphic (SNN) integration will cite A08 as pre-change performance baseline
- Security scan & secret rotation policy to extend A03 groundwork

---
All entries append-only; discrepancies between AUDIT_INDEX and AUDIT_LOG.md should trigger integrity review.
