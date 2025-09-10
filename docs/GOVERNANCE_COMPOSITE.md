# Governance Composite Signal & Adaptive Weighting

## Summary
The governance composite is a bounded (0..1) metric combining a precision proxy (rolling SNN unique ratio) and an exposure component (normalized current exposure risk vs baseline). It drives adaptive adjustments to `detection.temporal.weight` under guarded hysteresis and cooldown constraints.

Formula (conceptual):
```
composite = w_precision * snn_unique_ratio_rolling + w_exposure * min( (exposure_current / exposure_baseline) / 2.0 , 1.0 )
```
Weights default to `precision=0.6`, `exposure=0.4` and are normalized if overridden.

## Runtime Parameters
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `governance.signal.weights` | object | `{precision:0.6, exposure:0.4}` | Blend weights (precision + exposure) |
| `governance.composite.high_threshold` | float | 0.75 | Upper composite trigger threshold |
| `governance.composite.low_threshold` | float | 0.35 | Lower composite trigger threshold |
| `governance.composite.hysteresis` | float | 0.05 | Additional buffer preventing oscillation |
| `governance.composite.cooldown_s` | int | 900 | Minimum seconds between applied adjustments |
| `governance.composite.max_step_frac` | float | 0.15 | Max fractional change of current weight per step |
| `governance.composite.max_abs_delta` | float | 0.1 | Absolute cap on a single change |
| `governance.composite.min_weight` | float | 0.05 | Lower bound for temporal weight |
| `governance.composite.max_weight` | float | 0.6 | Upper bound for temporal weight |
| `governance.shadow_mode` | bool | true | When enabled, logs candidate adjustments without applying |
| `governance.weight.max_adjust_per_hour` | int | 3 | Rate limit on applied adjustments |

Temporal weight key currently adjusted: `detection.temporal.weight` (alias in code path may map to `fusion.weight.temporal` depending on consolidation—update if unified later).

## Adaptation Algorithm (High Level)
1. Recompute composite each governance cycle using latest SNN unique rolling gauge + exposure total risk ratio.
2. If composite > `high_threshold + hysteresis` and cooldown/rate limits pass: propose increasing temporal weight.
3. If composite < `low_threshold - hysteresis` propose decreasing temporal weight.
4. Proposed delta = min(`max_step_frac * current_weight`, `max_abs_delta`). Direction applied accordingly.
5. Clamp new weight to `[min_weight, max_weight]`.
6. If `shadow_mode=true`: skip persistence; log intent (audit trail) and emit governance decision metric only.
7. On success: update runtime param (audited), emit `FUSION_WEIGHT_UPDATES_TOTAL{strategy='governance_composite'}` and record last adjustment timestamp.

## Safety Guards
- Hysteresis band avoids flip-flopping around thresholds.
- Cooldown enforces temporal spacing between changes.
- Max adjustments/hour ensures rate limiting even if noisy composite.
- Bounded absolute and relative deltas prevent large jumps.
- Shadow mode allows dry-run validation before activation.

## Metrics
| Metric | Type | Purpose |
|--------|------|---------|
| `neuron_governance_composite_signal` | Gauge | Current composite value (0..1) |
| `neuron_fusion_weight_updates_total{strategy='governance_composite'}` | Counter | Count of applied adjustments |
| `neuron_fusion_temporal_weight` | Gauge | Current temporal fusion weight |

## Audit Trail
Parameter changes are appended to `audit/AUDIT_LOG.md` lines beginning with `PARAM_CHANGE`. Temporal weight changes can be parsed to reconstruct adjustment sequence (the reporting layer builds a sparkline from this log).

## Enabling Active Mode
```
PATCH /admin/params/update {"key":"governance.shadow_mode","value":false,"reason":"activate_adaptation"}
```
(Use your admin key; actual endpoint: `/admin/params/update` with JSON payload.)

## Operational Recommendations
- Observe at least one full day in shadow mode to validate composite volatility.
- Tune thresholds so that typical steady-state sits between low/high bands.
- Adjust `max_step_frac` downward (<0.1) if system exhibits sensitivity to weight shifts.

## Future Enhancements
- Incorporate retrieval drift & false positive surrogate metrics directly.
- Add exponential smoothing to exposure component to reduce sharp spikes.
- Multi-tenant composite segmentation once per-tenant exposure slices exist.
