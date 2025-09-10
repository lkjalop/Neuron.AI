# Isolation Forest SOC Operations Guide

Date: 2025-09-03
Status: Introduced Phase 4 Preview (A13 follow-on) – Ensemble diversity enhancement.

## Purpose
Adds an unsupervised tree-based anomaly detector to complement statistical baseline, SNN prototype, and temporal components. Targets detection of global outliers and distributional tail events that may not breach rolling z-score thresholds.

## When It Fires
The detector will produce anomalies when either:
1. Model prediction labels the event as an outlier (IsolationForest `predict` = -1), OR
2. Extreme single-feature magnitude heuristic triggers (`abs(value) > 6.0`) ensuring deterministic capture of severe spikes in low-dimensional feeds.

## Key Runtime Parameters (Prefix `iforest.*`)
| Param | Description | Typical Value |
|-------|-------------|---------------|
| `iforest.enable` | Master toggle | true/false |
| `iforest.buffer_size` | Sliding window of recent samples per tenant | 512 |
| `iforest.retrain_interval_events` | Minimum new samples before retrain (unless first train) | 128 |
| `iforest.retrain_interval_s` | Minimum seconds between retrains | 30 |
| `iforest.min_train` | Minimum samples to allow first model fit | 32 |
| `iforest.n_estimators` | Number of trees | 50–100 |
| `iforest.max_samples` | Subsample size per retrain (capped by buffer) | 256 |
| `iforest.contamination` | Expected anomaly proportion (guides threshold) | 0.05–0.15 |
| `iforest.random_seed` | Determinism for trees | 42 / test-specific |
| `fusion.weight.iforest` | Fusion weight in `weighted_sum` strategy | 0.1–0.4 |

## Fusion Interaction
In `weighted_sum` strategy the normalized Isolation Forest score contributes via `w_if`. Suppression thresholds still apply globally; if suppressed the anomaly may be omitted from fused results but still increment raw detector metrics.

## Operational Playbook
| Scenario | Symptom | Action | Escalation |
|----------|---------|--------|------------|
| No anomalies after deployment | 0 Isolation Forest anomalies for extended period while baseline/SNN firing | Verify `iforest.enable` true; check buffer growth; reduce `iforest.min_train` or contamination slightly | If still zero with obvious outliers, capture sample events & escalate to engineering (model fit path) |
| Excess anomalies | High volume vs baseline | Lower `fusion.weight.iforest`; decrease `iforest.contamination` (makes model stricter) | If persistent, review feature scaling / drift |
| Retrain too frequent | CPU load spikes, many retrain logs | Increase `iforest.retrain_interval_events` or `_s`; reduce `buffer_size` | Escalate if still > expected SLO (e.g., >1 retrain / min) |
| Missed extreme spike | Known >10σ value not flagged | Confirm heuristic path; ensure feature present (registry). If custom feature name not in canonical list, add mapping or pass as single numeric | Escalate with event payload & hash |

## Metrics (If Exposed)
| Metric | Meaning |
|--------|---------|
| `anomalies_total{detector="iforest"}` | Count of emitted anomalies |
| `detector_retrains_total{detector="iforest"}` | Model refits |
| `detector_training_seconds{detector="iforest"}` | Fit time distribution |

## Troubleshooting Checklist
1. Confirm enable param: `/admin/params` includes `iforest.enable: true`.
2. Check sample size: buffer length >= `iforest.min_train`.
3. Validate contamination: too low may suppress anomalies (try 0.1 for mixed distributions).
4. Inspect feature content: numeric values present; if using custom key not in `feature_order()`, confirm fallback engaged (single key accepted).
5. Force test event: inject `{"value": 9.5}` via `/ingest` (inline detect) for tenant and confirm anomaly return.

## Change Control
Any adjustment to default contamination, heuristic threshold, or fusion weight must be recorded via parameter update (automatically logged in `audit/param_changes.log`).

## Security & Integrity
Model retraining uses only recent in-memory buffer; no persistence. Tamper impact limited to transient false positives/negatives; mitigated by fusion diversity and audit of parameter changes.

## Future Enhancements
- Per-feature importance export (tree path frequency)
- Adaptive contamination based on rolling anomaly precision proxy
- Buffer stratification (time-decay weights)

---
Owner: Detection Engineering
Review Cadence: Quarterly or upon Phase 4 benchmark shifts.
