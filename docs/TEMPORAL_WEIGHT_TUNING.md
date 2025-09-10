# Adaptive Temporal Weight Tuner Guide

Status: Implemented (A13 Batch) – Advisory Document (Not Canonical)
Owner: Fusion / Temporal Subsystem
Related Amendments: A13 (Phase 4 Early Fusion & Temporal Intelligence Expansion)

## 1. Purpose
The temporal weight tuner autonomously adjusts the contribution of temporal anomaly signals in the fusion score to maintain an uplift improvement band while constraining noise. It prevents manual micromanagement of temporal scaling, enforcing guardrails to avoid overfitting or oscillatory behavior.

## 2. Conceptual Model
Let:
- B = baseline detector anomaly contribution baseline (reference precision/recall)
- T = temporal detector contribution (variable weight * raw temporal score)
- U = uplift ratio = (anomalies_detected_with_temporal / anomalies_detected_without_temporal) (proxy from fused vs baseline-only path under controlled windows)
- Target band: [target_uplift - tolerance, target_uplift + tolerance]

The tuner nudges `fusion.weight.temporal` toward sustaining U within the band. When uplift is below lower bound it increases weight; when above upper bound (excess risk of noise) it may reduce or clamp. If U is within band it applies no change (cooldown safe period continues).

## 3. Runtime Parameters (Prefix: `fusion.temporal.*`)
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| enabled | bool | true | Master toggle for tuner logic. |
| target_uplift | float | 1.25 | Desired multiplicative anomaly uplift vs baseline. |
| tolerance | float | 0.15 | Acceptable +/- band around target before adjustment triggers. |
| max_step | float | 0.05 | Max proportional delta to apply per adjustment (before abs clamp). |
| max_abs_delta | float | 0.02 | Absolute safety clamp on per-cycle adjustment magnitude. Smaller of (current_weight*max_step, max_abs_delta) used. |
| cooldown_s | float | 60 | Minimum seconds between adjustments (prevents thrash). |
| min_baseline | int | 10 | Minimum baseline anomaly count sample size before tuner acts. |
| weight_min | float | 0.0 | Hard lower bound on temporal fusion weight. |
| weight_max | float | 0.5 | Hard upper bound to limit noise risk. |
| seed_weight | float | 0.0 | Initial starting weight if unset; allows gradual emergence of temporal influence. |
| window_min | int | 30 | Minimum number of fused decisions in a tuning window (if implemented). |
| window_max | int | 500 | Soft cap on window size to avoid stale signals. |

(If some window params not yet in code, treat as reserved for evolution.)

## 4. Algorithm Summary
1. Collect anomaly contribution counters for baseline-only and fused (with temporal) contexts.
2. Compute uplift ratio U (guard: if baseline_count < min_baseline -> exit).
3. Determine band: [L, H] = [target_uplift - tolerance, target_uplift + tolerance].
4. If U within [L, H]: do nothing (record stability / cycle metrics only).
5. Else compute direction:
   - If U < L -> direction = +1 (increase weight)
   - If U > H -> direction = -1 (decrease weight)
6. Raw proposed_delta = current_weight * max_step * direction
7. Clamp |proposed_delta| <= max_abs_delta
8. new_weight = clamp(current_weight + proposed_delta, weight_min, weight_max)
9. Persist updated weight (runtime param set + audit entry) and emit metrics.
10. Record cycle duration & window size; reset counters if using sliding window.

## 5. Metrics
| Metric | Type | Labels | Notes |
|--------|------|--------|-------|
| fusion_temporal_tuner_cycle_seconds | histogram | none | Duration between adjustment evaluation cycles. |
| fusion_temporal_tuner_window_size | gauge | none | Number of fused decisions evaluated in last cycle. |
| fusion_temporal_tuner_adjustments_total | counter | direction={increase,decrease,noop} | Adjustment direction accounting. (noop optional) |
| precision_proxy_rate | gauge | detector | Temporal false-positive proxy gating input. |
| fusion_temporal_weight | gauge | none | (If exposed) Current temporal weight (may be in param export instead). |

## 6. Gating & Safety Interactions
- Precision Proxy: If temporal precision proxy rate exceeds configured threshold, temporal path contribution can be suppressed or scaled to zero before fusion weight update (prevents penalizing tuner for suppression state).
- Cooldown: Prevents repeated micro-adjustments; each attempt checks time since last successful change.
- Bounds: weight_min / weight_max act as absolute caps independent of uplift extreme deviations.

## 7. Operational Playbook
| Scenario | Observation | Action |
|----------|-------------|--------|
| Weight stuck at 0 | Uplift calc suppressed by precision gating or insufficient baseline anomalies | Verify precision proxy threshold & baseline_count >= min_baseline; if gating persistent, investigate temporal noise causes. |
| Oscillation near band edges | Frequent +- toggling every cooldown | Reduce max_step OR increase tolerance; optionally raise cooldown_s. |
| Persistent uplift deficit | Weight at max without reaching target | Investigate temporal model quality; consider raising weight_max cautiously after noise analysis; check gating ratio. |
| Excess uplift (high noise risk) | U >> target and weight near max | Confirm FP proxy not elevated; consider lowering weight_max or adding stricter gating. |
| Slow convergence | Many cycles with tiny changes | Increase max_step slightly OR raise seed_weight; ensure baseline_count not marginal. |

## 8. Troubleshooting Checklist
1. Confirm metrics scraping (tuner histogram shows recent observation).
2. Inspect audit `param_changes.log` for recent weight updates; absence with cycles indicates band stability or gating.
3. Validate uplift computation inputs (baseline anomalies vs fused anomalies); mis-count leads to frozen adjustments.
4. Check precision proxy gauge for temporal path; sustained elevation explains gating suppression.
5. Ensure runtime time source monotonic and cooldown_s not misconfigured (e.g., very large value).

## 9. Rollback Procedure
If temporal path causes instability or elevated false positives:
1. Set `fusion.temporal.enabled=false` (audited) OR directly set `fusion.weight.temporal=0.0`.
2. Optionally raise `precision_max_rate` threshold temporarily to disentangle gating side-effects during analysis.
3. Capture snapshot: export tuner metrics + uplift counters for root cause record.
4. Re-enable in staged fashion: set seed_weight to low non-zero, observe 2–3 cycles, then allow tuner autonomy.

## 10. Audit & Integrity
- Every weight change is recorded in `audit/param_changes.log` with timestamp, old/new values, reason.
- A13 amendment documents introduction; future algorithmic changes require new amendment referencing this guide.
- Recommend periodic hash of this doc if used in governance workflows (non-canonical currently).

## 11. Future Enhancements
| Idea | Benefit | Considerations |
|------|---------|----------------|
| Success/failure classification metric | Faster anomaly in tuning logic regression detection | Add outcome labels per cycle |
| Multi-objective tuner (precision & uplift) | Balanced improvements | Requires richer signal instrumentation |
| Adaptive step sizing (PID-like) | Faster convergence with stability | Complexity vs transparency trade-off |
| Persistent window state across restarts | Stable behavior after redeploy | Requires param store or state serialization |

## 12. Reference Pseudocode
```
if not enabled: return
if now - last_adjust_ts < cooldown_s: record_cycle(); return
if baseline_count < min_baseline: record_cycle(); return
U = fused_anoms / max(baseline_anoms,1)
if L <= U <= H: record_noop(); record_cycle(); return
direction = +1 if U < L else -1
proposed = current * max_step * direction
proposed = clamp_mag(proposed, max_abs_delta)
new_w = clamp(current + proposed, weight_min, weight_max)
if new_w != current: set_param(new_w); emit_adjust(direction)
record_cycle()
```

## 13. Quick Verification Steps
Run controlled synthetic batch with temporal anomalies disabled then enabled:
1. Capture baseline anomaly count N.
2. Enable temporal path with seed_weight > 0.
3. After window, verify uplift ~ target band; if below, confirm tuner increased weight.
4. Check param changes log reflects adjustment with timestamps spaced by >= cooldown_s.

## 14. FAQ
Q: Why both `max_step` and `max_abs_delta`?  
A: Provides proportional scaling early (when weight large) while ensuring absolute safety cap for small or large weights—prevents overshoot in either regime.

Q: Does tuner modify other detector weights?  
A: Currently no; baseline & SNN weights static unless separate governance action taken.

Q: How is uplift computed if suppression disables temporal contribution?  
A: Suppressed intervals should be excluded or counted distinctly; current implementation may treat suppressed contribution as zero—interpret uplift carefully during sustained suppression.

---
End of Guide.
