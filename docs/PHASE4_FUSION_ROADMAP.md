# Phase 4 Fusion Roadmap & Transition Summary

## Summary
Phase 4 expanded the detection stack from isolated detectors to a governed fusion layer with strategy selection, overlap/unique attribution metrics, suppression controls, and early safety alerts. This enables experimentation with multi-detector ensembles (Baseline + SNN) while enforcing guardrails against over-suppression and silent regression.

## Objectives Achieved
Completed (Phase 4 current):
1. Fusion strategies implemented: `pass_through`, `baseline_priority`, `consensus_only`, `weighted_sum` (new).
2. Weighted sum decision score + suppression threshold (`fusion.weighted_sum.suppress_threshold`).
3. Fusion metrics suite: overlap/unique ratios, rolling SNN unique, suppressed counts, suppression rate & alerts, source combos.
4. Precision proxy instrumentation: noise window tagging (`synthetic_pattern`), false positive counters, rate gauge.
5. Residual contribution instrumentation: per-event residual activity + rolling mean gauge, comparison script (`scripts/compare_residual.py`).
6. Runtime param governance: enumeration guard for `detection.fusion.strategy`; fusion weight params audited.
7. Unit tests: weighted sum scoring & suppression, precision proxy window counting, audit logging for weight changes.
8. SOC & MITRE-facing documentation integrated into `FUSION_ARCHITECTURE.md` (education section + mapping).
9. Refreshed fusion architecture doc (strategy table, metrics, roadmap). 

In Progress / Deferred:
10. Adaptive weight / suppression auto-tuning (Phase 5+).
11. Confidence calibration layer for SNN norm distribution alignment.
12. Rule pack integration & explicit rule-gated strategy variant.

## Key Metrics & Definitions
| Metric | Meaning | Governance Use |
|--------|---------|----------------|
| neuron_fusion_overlap_ratio | Fraction of events where both detectors agreed on anomaly | Detects divergence / correlation drift |
| neuron_fusion_baseline_unique_ratio | Fraction anomalies only baseline produced | Baseline signal uniqueness |
| neuron_fusion_snn_unique_ratio | Fraction anomalies only SNN produced | SNN contribution |
| neuron_fusion_snn_unique_ratio_rolling | Rolling SNN unique contribution proxy | Change detection / drift |
| neuron_fusion_suppressed_total | Total anomalies suppressed by fusion strategy | Volume tracking |
| neuron_fusion_suppression_rate | Rolling ratio suppressed / (suppressed + emitted) | Over-suppression guard |
| neuron_fusion_suppression_alerts_total | Count of suppression rate breaches | Alerting & auto-fallback trigger |
| neuron_precision_proxy_rate | False positive rate during synthetic quiet windows | Precision guard / threshold tuning |
| neuron_precision_proxy_false_positive_total | Raw anomaly count inside noise windows | Input to rate |
| neuron_snn_residual_contrib_mean | Rolling mean of positive forecast residual contributions | Temporal novelty intensity |

## Strategy Semantics
- pass_through: Union of detectors (no suppression) – baseline compatibility mode.
- baseline_priority: Baseline anomalies always included; SNN anomalies additive (de-dup by identity heuristics).
- consensus_only: Emit only overlapping anomalies (precision-biased mode).
- weighted_sum: Linear blend of baseline indicator & normalized SNN score with suppression of low-score SNN-only anomalies.

## Suppression Governance
Suppression gate (weighted sum): SNN-only anomaly suppressed if blended `decision_score < fusion.weighted_sum.suppress_threshold`.
Rolling suppression rate computed over configurable window (`fusion.precision_window`).
If `suppression_rate > fusion.suppression_alert_rate`, alert counter increments; future automation may raise suppression threshold or downgrade strategy.

## Risks & Mitigations
| Risk | Mitigation |
|------|-----------|
| Over-suppression hides true anomalies | Suppression rate alert + strategy fallback plan |
| Detector drift reduces overlap | Monitor overlap ratio trend; investigate threshold tuning |
| Parameter changes introduce instability | Audit trail + param change tail in gate report |
| Latent performance regression | (Planned) latency histograms & resource gauges |
| Unbounded SNN noise in quiet periods | Precision proxy FP rate monitoring + raise threshold playbook |
| Residual inflation causing false uplift | Rolling residual mean gauge to detect abnormal jumps |

## Transition to Phase 5
Phase 5 introduces executive KPIs, latency/resource instrumentation, multi-tenant governance views, and automated strategy fallback triggers.

### Planned Phase 5 Deliverables (Updated)
1. Executive KPI endpoint `/executive/kpis` with suppression rate, precision proxy rate, uplift ratio, residual mean.
2. Detector latency histogram + ingestion throughput & queue depth dashboards.
3. Adaptive suppression threshold tuner (precision proxy target band) + optional PID-like controller.
4. Auto-fallback: sustained high suppression OR proxy rate breach => switch to conservative strategy.
5. Rule pack (threat intel heuristics) integration feeding fusion as third signal.
6. Confidence calibration (percentile / isotonic) for SNN activity normalization.
7. TFT (Temporal Fusion Transformer) prototype replacing stub forecaster for residual scoring.
8. Analyst Quick Card & MITRE mapping table auto-generated in docs.
9. Extended audit: hash of fusion config + doc section anchors stored in gate report.

### Open Questions (Tracked)
- Do we incorporate adaptive thresholds for suppression using statistical bounds? (Candidate post-Phase 5.)
- Should we weight detectors based on recent precision proxy? (Future adaptive fusion strategy.)
 - Automatic residual gating if residual mean spikes beyond learned baseline distribution?
 - Cross-tenant fusion heuristics vs per-tenant parameters?
 - Minimum evaluation window size before enabling adaptive controller?

## SOC Enablement Plan (Phase 4 -> 5)
Artifacts:
- Quick Card (KPIs + definitions) – to be added as `docs/SOC_TRAINING.md` (Phase 5 early).
- MITRE Mapping Table – integrate into `SOC_ANALYST_GUIDE.md` refresh.
- Escalation Playbook: precision proxy breach & suppression spike responses.

Playbook Seeds:
1. Precision proxy rate > 0.05 for >50 noise windows: raise suppression threshold by +0.05 and re-evaluate after 200 events.
2. Suppression rate > 0.85 for 2 consecutive windows: downgrade to `baseline_priority` and open investigation ticket.
3. Residual mean contribution doubling vs prior rolling median: flag potential temporal model drift.

Next-Step Automation Hooks:
- Parameter auto-adjust service consuming metrics endpoint snapshots.
- Dashboard annotation API for SOC to record manual threshold interventions.

---
Prepared: This document is hashed as part of the canonical documentation set for integrity monitoring.
