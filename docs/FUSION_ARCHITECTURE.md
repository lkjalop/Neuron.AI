# Fusion / Arbitration Architecture (Phase 4 Draft)

Status: Phase 4 Active (Weighted Sum + Temporal Confidence + Precision Gating Integrated)

## 1. Objectives & Constraints
| Objective | Description | Constraint / Guardrail |
|-----------|-------------|------------------------|
| Precision Protection | Never degrade precision >5% absolute vs baseline during fusion | Baseline retains veto in conflict if SNN-only confidence low |
| Uplift Retention | Preserve ≥15% recall uplift delivered by SNN | Track rolling uplift; auto-evaluate if <15% two cycles |
| Latency Budget | Added p95 inference cost <5 ms vs baseline-only path | Arbitration adds O(µs) scoring math only |
| Deterministic Audit | Fusion decision reproducible given artifacts and params | Decision record includes component scores & flags |
| Incremental Extensibility | Allow adding rule packs & future ML detectors | Abstraction: detector outputs standardized schema |
| Fail-Safe Fallback | If SNN disabled or fusion errors => baseline-only | Try/except around arbitration block + health flag |

## 2. Detector Output Normalization
Proposed per-detector anomaly result fields (subset):
```
{
  "detector": "baseline|snn|rulepackX",
  "score": float,            # detector-specific severity
  "confidence": float,       # normalized 0..1 (baseline=1.0 for accepted anomalies)
  "feature_count": int,
  "spike_density": float?,   # SNN only
  "latency_ms": float,
  "threshold": float?,
  "tags": ["mad_fallback", "resource_guard_reenable", ...]
}
```
Fusion will derive a standardized `component_score = f(score, confidence)`.

## 3. Fusion Strategies (Implemented + Experimental)
| Strategy | Param Value | Description | Pros | Cons | Current Status |
|----------|-------------|-------------|------|------|---------------|
| Pass Through | `pass_through` | Concatenate anomalies from detectors (legacy union) | Simple, transparent | No precision guard | Legacy/Eval |
| Baseline Priority | `baseline_priority` | Baseline anomalies always; SNN anomalies may be appended | Protects precision | Misses some unique SNN wins | Available |
| Consensus Only | `consensus_only` | Only anomalies where both detectors fire | High precision | Recall loss | Available |
| Weighted Sum + Suppression | `weighted_sum` | `decision_score = w_b*B + w_s*S (+ w_t*T when gated)`; suppress low-score SNN-only; temporal requires HIGH/CRITICAL band | Tunable trade-off, guarded, extensible | Weight drift risk without tuner | Active (Phase 4) |

## 4. Scoring & Confidence Contract
Normalization functions:
```
baseline_norm = 1.0  # binary anomaly acceptance => confidence=1
snn_norm_score = min(1.0, max(0.0, (activity - threshold) / (threshold * 2)))
confidence_band(snn_norm_score):
  >=0.66 => HIGH
  0.33–0.66 => MEDIUM
  <0.33 => LOW
```
`decision_score` (Weighted Sum active strategy baseline + snn):
```
decision_score = w_b * baseline_indicator + w_s * snn_norm_score
# baseline_indicator in {0,1}
# snn_norm_score = clip((activity - threshold)/(threshold*2), 0..1)
```

Temporal Extension (now implemented):
```
if temporal_anomaly and temporal_confidence in {HIGH,CRITICAL} and precision_proxy_rate_temporal <= fusion.temporal.precision_max_rate:
  decision_score += w_t * temporal_norm   # temporal_norm = clamp(temporal_score, 0..1)
else:
  temporal influence gated (anomaly still surfaced with fusion_components.temporal_gated=True)
```
Suppression Guard:
```
if baseline_indicator == 0 and decision_score < fusion.weighted_sum.suppress_threshold:
  suppress anomaly (count in FUSION_SUPPRESSED_TOTAL)
```
`source_flags` example: `{"baseline": true, "snn": true, "snn_confidence": "HIGH"}`.

## 5. Conflict Handling Matrix
| Baseline | SNN | SNN Confidence | Action (Rule-Gated) | Rationale |
|----------|-----|----------------|---------------------|-----------|
| Neg | Neg | Any | No anomaly | Agreement |
| Pos | Pos | Any | Emit anomaly (baseline authoritative) | Concordant |
| Pos | Neg | Any | Emit anomaly (baseline authoritative) | Protect precision |
| Neg | Pos | LOW | Suppress (log suppressed_snn_low_conf) | Avoid low-value noise |
| Neg | Pos | MEDIUM | Emit with tag `fusion_added` if spike_density in band | Balanced uplift |
| Neg | Pos | HIGH | Emit (always) | High-confidence novel anomaly |

## 6. Resource Impact & Fallback
Arbitration layer operations: set merges, small dict constructions, optional linear blend; expected <50µs per event in Python.
If any exception => log, increment `FUSION_ERRORS_TOTAL`, revert to baseline-only for that event.
If SNN disabled (guard cooldown) => arbitration short-circuits to baseline path.

## 7. Hooks for Phase 5
- Additional detectors (e.g., rule packs) simply produce normalized anomaly outputs.
- Confidence calibration module (Platt scaling or isotonic) for SNN scores.
- Ensemble explanation endpoint: returns per-detector contribution breakdown.

## 8. Metrics (Implemented Subset)
```
FUSION_DECISIONS_TOTAL{outcome="overlap|baseline_only|snn_only|none"}
FUSION_SOURCE_COMBO_TOTAL{combo}
FUSION_OVERLAP_RATIO / FUSION_BASELINE_UNIQUE_RATIO / FUSION_SNN_UNIQUE_RATIO
FUSION_SNN_UNIQUE_RATIO_ROLLING
FUSION_SUPPRESSED_TOTAL{strategy,detector}
FUSION_SUPPRESSION_RATE
PRECISION_PROXY_WINDOWS / PRECISION_PROXY_FALSE_POSITIVE / PRECISION_PROXY_RATE
SNN_RESIDUAL_ACTIVITY / SNN_RESIDUAL_CONTRIB_MEAN
TEMPORAL_VARIANCE_MEAN / TEMPORAL_ATTENTION_SCORE
TEMPORAL_RESIDUAL_NORM / TEMPORAL_RESIDUAL_P95
TEMPORAL_CONFIDENCE_BAND{band}
FUSION_TEMPORAL_WEIGHT / FUSION_TEMPORAL_CONTRIBUTION
```
Deferred: Fusion latency histogram, adaptive temporal weight update counter (separate from reuse of FUSION_WEIGHT_UPDATES_TOTAL).

## 9. Integrity & Audit Mapping
- Store `fusion_strategy` and parameter weights (if S2) in runtime params with audit trail.
- Gate Report (Phase 4) includes hash of this file and metrics snapshot.
- Fusion change process: modify doc => hash diff => audit entry referencing old hash with reason (e.g., "add rule pack", "weight retune").

## 10. Implementation Roadmap (Updated)
Completed (Updated):
1. Strategy param + enumeration guard.
2. Weighted sum strategy + suppression threshold.
3. Temporal anomaly integration (confidence-band gating + additive weight).
4. Overlap/unique/suppression metrics.
5. Precision proxy instrumentation and rate gauge.
6. Temporal residual calibration (quantile store) & confidence band emission.
7. New temporal metrics (variance/attention/residual norm/p95/conf bands) & fusion temporal weight gauges.
8. Unit tests covering weighted sum, suppression, and temporal gating.

Upcoming:
7. Adaptive weight tuning loop (Phase 5).
8. Confidence calibration layer.
9. Rule pack integration -> rule-gated explicit strategy variant.
10. Executive dashboard visualization & KPI alignment.

## 11. Open Questions
- Do we need per-tenant fusion strategies? (Deferred; start global.)
- Should suppressed SNN anomalies be stored for offline learning? (Likely yes; add ring buffer.)
- Calibration: Do we align SNN activity distribution via percentile mapping first? (Evaluate after initial metrics.)
 - Automatic suppression threshold tuning from precision proxy target.

## 12. SOC Analyst Enablement & MITRE Mapping
Plain Explanation:
"Fusion blends a stable statistical detector with a temporal pattern detector. We only trust temporal-only signals when their confidence passes a bar, protecting precision while increasing coverage of stealthy time-based behaviors."

Key KPIs for SOC:
- Uplift Ratio: additional valid anomalies vs baseline.
- Precision Proxy Rate: false positives in quiet windows (keep low).
- Suppression Rate: proportion of low-confidence temporal signals filtered out.
- Residual Mean Contribution: average additive value from forecast residual (indicates temporal novelty intensity).

MITRE Technique Examples:
- Periodic beaconing (T1071): captured via periodic shift anomalies.
- Exfiltration burst (TA0010): burst pattern windows.
- Slow privilege drift (multiple tactics) via gradual drift sequence.

Escalation Playbook Trigger Examples:
- If Precision Proxy Rate > 0.05 for 50 noise windows: raise suppression threshold by +0.05.
- If Uplift Ratio < 1.1 for 2 evaluation cycles: review SNN threshold / weights.

Education Path (Non-Technical):
1. 1-page Quick Card: KPIs + meanings.
2. MITRE Mapping Table: pattern -> hypothesis -> suggested investigation.
3. Dashboard Walkthrough: how each tile informs triage.

Temporal Fusion Transformer (Future):
We will evolve from deterministic TFT-lite (currently providing residual norm + per-dim residual vector) toward a probabilistic temporal fusion transformer producing per-dimension predictive distributions (mean + variance). Benefits: richer residual semantics, calibrated uncertainty, and multi-feature temporal correlation enabling granular anomaly taxonomies (e.g., "rhythmic beacon" vs "shift drift" vs "phase-shift burst").

---
Hash this file prior to Phase 4 gate.

## 13. Forward Roadmap: Temporal Fusion Transformers & Agent Expansion

Temporal Fusion Transformer (TFT) Integration Steps:
1. Data Contracts: Promote `VectorSequenceBuffer` window -> tensor adapter (shape: [T, F]).
2. Feature Enrichment: Add positional indices + simple time deltas (synthetic if absent) for transformer consumption.
3. Model Stub -> Module: Create `core/temporal/models/tft_stub.py` with deterministic linear attention block (no external deps first pass).
4. Residual Semantics: Output predicted next-step vector + per-dim residual; derive anomaly score via robust z/MAD over residual distribution.
5. Fusion Weighting: Introduce adaptive temporal weight param application in arbitrator (if temporal anomaly only) using `detection.temporal.weight`.
6. Calibration: Maintain rolling residual quantiles to map raw residual norms to confidence.
7. Resource Guards: Extend temporal guard to track model forward latency & memory footprint (estimate parameter count * dtype bytes).

Agent Expansion Path:
1. Policy Signals: Feed fusion & temporal metrics (suppression rate, overlap ratio trend) into policy engine context for proactive recommendations.
2. Decision Logging: Already audited; extend schema with `confidence`, `context_span_ids` referencing retrieval hits.
3. Retrieval Augmentation: Generate temporal anomaly narrative by querying corpus with enriched semantic keys (detector=temporal, reason=variance|attn, feature=top_feature).
4. Multi-Agent Roles: Introduce `AnalystAssistant` (summarization) and `GuardRailAgent` (monitors precision proxy & triggers calibration suggestions) via the existing bus.
5. Closed-Loop Calibration: Agent proposes param deltas (e.g., lower SNN threshold) -> queued for human approval -> applied through audited runtime param update.
6. Safety Net: All autonomous actions remain read-only until risk tier lowered via governance flag (future `agent.autonomy.level`).

Design Principles (Forward):
- Deterministic first, probabilistic later.
- Metrics before model: instrumentation precedes complexity.
- Human approval gates on irreversible or precision-impacting actions.

KPIs Recently Added:
- `TEMPORAL_RESIDUAL_P95`, `TEMPORAL_ATTENTION_SCORE`, `TEMPORAL_CONFIDENCE_BAND{band}`.
- `FUSION_TEMPORAL_WEIGHT`, `FUSION_TEMPORAL_CONTRIBUTION`.

Upcoming KPIs:
- Calibration cycle success ratio (reduction in false positives next N windows).
- Agent recommendation acceptance rate.
- Temporal precision proxy rate (once temporal participates in noise windows formally).

Open Risks:
- Overfitting temporal encoder to synthetic patterns (mitigate with holdout noise sequences).
- Retrieval staleness (schedule corpus rebuild cadence & freshness metric).
- Agent action escalation loops (enforce cool-down on repeated identical suggestions).
