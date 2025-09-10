# SOC Temporal Quick Card

## Purpose
Fast reference for adjusting temporal detection influence and validating changes safely.

## Key Runtime Parameters
- `detection.temporal.enable_transformer` – Registers temporal detector scaffold.
- `detection.temporal.simple_model` – Enables simple variance/attention/TFT encoder anomaly emission.
- `detection.temporal.encoder` – `variance | attn | tft`.
- `detection.temporal.weight` – Fusion additive temporal weight for `weighted_sum` strategy.
- `fusion.temporal.tuner.enabled` – Auto-adjust temporal weight toward uplift target.
- `fusion.temporal.tuner.target_uplift` – Desired temporal anomaly contribution relative to baseline.
- `fusion.temporal.precision_max_rate` – Gating threshold for temporal influence if precision proxy too noisy.

## Observability Metrics
- Temporal anomaly quality: `neuron_temporal_confidence_band_total` (band distribution)
- Weight influence: `neuron_fusion_temporal_weight`, `neuron_fusion_temporal_contribution`
- Tuner health: `neuron_fusion_temporal_tuner_uplift_ratio`, `neuron_fusion_temporal_tuner_adjustments_total`
- Calibration freshness & stability: `neuron_temporal_calibration_freshness_seconds`, `neuron_temporal_residual_variance`
- Precision risk: `neuron_precision_proxy_rate` (detector=temporal)

## Change Workflow
1. Baseline Snapshot
   - Record current values of uplift ratio, temporal weight, suppression rate, precision proxy rate.
2. Safe Adjustment
   - Small manual bump: update `detection.temporal.weight` (e.g. +0.05) with rationale.
   - OR enable tuner: set `fusion.temporal.tuner.enabled=true`.
3. Monitor 2–3 tuning cycles
   - Expect uplift to trend toward target band (± tolerance) without rapid oscillation.
4. Precision Guard
   - If `precision_proxy_rate(temporal)` spikes above threshold, reduce weight or raise threshold cautiously.
5. Calibrate / Rollback
   - If suppression rate surges or false positives increase, rollback last param (audit log provides previous value).

## Rollback Procedure
1. Inspect `audit/param_changes.log` for last good hash.
2. Reapply prior param with `update_param`.
3. Confirm metrics convergence within previous baseline ranges.

## Quick Triage Scenarios
| Symptom | Likely Cause | Action |
|---------|--------------|--------|
| Low uplift ratio | Weight too low / gating active | Increase weight or reduce precision gate threshold |
| High suppression rate | Baseline dominance or noisy temporal | Check temporal variance / lower weight |
| Stale calibration freshness | Low event volume | Extend stale threshold or inject warm-up events |
| High residual variance | Unstable signal | Temporarily gate or widen threshold |

## Approval Checklist Before Production Change
- [ ] Metrics stable over N>200 events
- [ ] No sustained precision proxy spike
- [ ] Calibration freshness < stale threshold
- [ ] Audit entry recorded with clear reason

## References
- Fusion architecture: `docs/FUSION_ARCHITECTURE.md`
- NEURON phases: `docs/NEURON_PHASES.md`
