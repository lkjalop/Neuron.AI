# NEURON CENTRAL DOGMA (Immutable)

> Version: 2025-09-02 - Do not edit directly. Create an addendum if modification is required.

This AI security intelligence platform exists to **empower human defenders, augment judgment, reduce toil, and accelerate accurate, ethical decision-making**. It **must not**:

1. Replace human accountability for critical security or safety decisions.
2. Obscure reasoning: explanations must remain accessible, reviewable, and auditable.
3. Sacrifice privacy, proportionality, or lawful boundaries for detection performance gains.
4. Operate autonomously on irreversible actions (e.g. destructive isolation) without explicit policy or human override capability.
5. Degrade user trust through undisclosed model behavior, covert data exfiltration, or hidden enrichment pipelines.

Positive Commitments:
- Human-first triage: predictions and agent verdicts are decision support, not final truth.
- Observability and provenance everywhere: every automated action is traceable, reversible, and justified.
- Lean & frugal innovation: optimize for clarity, security, and measurable value over speculative complexity.
- Progressive enhancement: experimental features run in shadow/simulation until validated.
- Ethical posture: alignment with international AI governance norms (ISO 42001, NIST AI RMF, EU AI Act proportionality principles) as they stabilize.

Change Process:
- Any proposal to alter this dogma must be logged in `audit/AUDIT_LOG.md` with: Rationale, Impact Analysis, Stakeholder Sign-off placeholders.

## Addendum: Temporal Buffer & Guard Scaffold (Informational)

The temporal modeling pathway (Phase scaffold) introduces:

- Legacy scalar sequence buffer (`GLOBAL_SEQUENCE_BUFFER`) supporting residual forecasting in SNN.
- Vector normalized buffer (`VectorSequenceBuffer`) populated per event with canonical ordered feature vectors (see `core.features.registry`).
- Metrics: `neuron_temporal_latency_seconds`, `neuron_temporal_guard_trips_total`, `neuron_temporal_buffer_ready_ratio` for readiness and guard observability.
- Guard params: `temporal.guard.max_latency_s`, `temporal.guard.max_window` (memory guard reserved).
- Optional residual variance contribution (`temporal.residual.enable`) to augment baseline anomaly scoring.

Principles:
1. Backward compatibility for existing detectors.
2. Deterministic normalization via running min/max.
3. Observability precedes model complexity.
4. Gated rollout with runtime parameters to minimize regression surface.

Planned Next Steps (non-binding): light temporal encoder, drift-aware fusion weighting, memory guard activation, and agent-assisted temporal hypothesis explanations.
