# Insight Severity Interpretation

Date: 2025-09-03
Status: Draft (A17 scope)

## Purpose
Provide analysts and engineering with a consistent, transparent rubric for interpreting the `severity` field attached to each heuristic insight returned by `/insights`. Severity is an evidence-weighted, bounded (0..1) scalar used to prioritize follow-up investigations — it is NOT an automated action trigger.

## Global Principles
- Range: `0.0` = negligible concern, `1.0` = maximum modeled concern for that heuristic class.
- Local Scaling: Each heuristic uses a domain-specific normalization; severities are **not** strictly comparable across unrelated categories (e.g., uplift vs quantile shift) but are stable within a category over time.
- Monotonicity: Higher underlying deviation from expected behavior never yields lower severity.
- Saturation: Designed so that extreme but plausible deviations reach or approach 1.0 without requiring pathological values.

## Heuristic Formulas
| Category | Formula (Conceptual) | Intuition | When ~0 | When ~1 |
|----------|---------------------|----------|--------|--------|
| `temporal_uplift` | deficit = max(0, 0.5*target - uplift); severity = deficit / (0.5*target) | Measures how far below half the target temporal uplift we are | uplift >= 0.5*target | uplift ≈ 0 |
| `calibration_stale` | over = freshness - threshold; severity = over / threshold (clamped 0..1) | Time since last calibration relative to stale limit | freshness <= threshold | freshness >= 2*threshold |
| `fusion_suppression_high` | (suppression_rate - alert_thr)/(1 - alert_thr) (clamped) | How far into the excessive suppression region we are | rate < alert_thr | sustained near 1.0 |
| `quantile_shift` | |delta_p99| / (4 * trigger_base) | p99 residual drift magnitude relative to trigger threshold | |delta| near trigger_base | |delta| >= 4*trigger_base |

Where `trigger_base = max(0.05*p99, 0.01)`.

## Interpretation Bands
These are advisory; adjust in dashboards / alerting policies as empirical precision is gathered.

| Severity Band | Range | Recommended Analyst Action |
|---------------|-------|----------------------------|
| Informational | 0.00 – 0.24 | Observe in routine dashboard scan; no ticket. |
| Watch | 0.25 – 0.49 | Add to watchlist; correlate with recent param or workload changes. |
| Investigate | 0.50 – 0.74 | Open lightweight investigation; capture metrics snapshots. |
| Action | 0.75 – 0.89 | Escalate to detection engineering; consider param adjustments. |
| Critical | 0.90 – 1.00 | Immediate action; potential disable/gate or threshold tuning. |

## Analyst Workflow Integration
1. Pull `/insights` for tenant.
2. Sort by `severity` descending within category clusters (temporal, fusion, calibration).
3. For top non-informational entries, cross-check:
   - Recent parameter changes (audit log)
   - Retrain counts or latency anomalies
   - Fusion decision distribution shifts
4. Document outcome and close or escalate.

## Calibration & Future Evolution
- Periodic Backtesting: Recompute severity distributions over historical incidents to refine band thresholds.
- Adaptive Scaling: Future work may adjust scaling factors based on false positive review outcomes (recorded via analyst feedback API TBD).
- Cross-Heuristic Prioritization: Potential composite risk score (weighted max) may be introduced; until then, treat categories independently.

## Limitations
- Heuristic, not probabilistic: Severity is not a calibrated probability.
- Static thresholds: Currently depends on configured params; dynamic baselining (e.g., EWMA of uplift variance) deferred.

## Change Control
Updates to formulas or bands will trigger a new audit entry (A17+). Maintain backward compatibility by exposing version metadata if formulas diverge materially.

---
Owner: Detection Engineering
Review Cadence: Monthly or upon new heuristic addition.
