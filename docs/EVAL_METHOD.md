# Evaluation Methodology

Version: 0.1

## Objectives
Provide statistically defensible evidence that advanced / composite detectors (e.g. SNN, fusion strategies) deliver material uplift versus the baseline statistical detector while controlling false positives and monitoring drift.

## Core Metrics
- Precision (PPV)
- Recall (TPR)
- Specificity (TNR)
- F1 Score (harmonic mean of precision & recall)
- False Positive Rate (FPR)
- Utility Score (custom weighted objective):
  U = w_p * Precision + w_r * Recall - w_fp * FPR
  Default weights: w_p=0.30, w_r=0.70, w_fp=0.20 (recall emphasized, FP cost penalized)

Rationale: Security anomaly triage often values missed-attack reduction (recall) while bounding alert fatigue (precision / FP rate).

## Statistical Procedures
### Bootstrap Confidence Intervals
- For each detector metric requiring uncertainty (F1, Utility), we perform B (default 1000) bootstrap resamples of event indices with replacement.
- Each resample recomputes the metric; distribution percentiles yield a (1-α) CI (default α=0.05).
- Non-parametric, distribution-agnostic, captures variance due to finite sample size.

### Paired Comparison (McNemar Test)
- Applied to baseline vs candidate binary event-level predictions.
- b = baseline correct & candidate wrong; c = baseline wrong & candidate correct.
- Small samples (b+c <= 25): exact binomial two-sided p-value.
- Larger: chi-square approximation with continuity correction.
- Interprets whether accuracy difference is statistically significant given paired structure.

### Practical vs Statistical Significance
- Report delta metrics (ΔF1, ΔUtility) alongside p-value.
- Require both: (a) utility CI lower bound > 0 improvement OR absolute uplift >= predefined threshold (e.g., ΔUtility ≥ 0.02) AND (b) McNemar p <= 0.05 OR strong operational justification.

## Gating / Promotion Criteria (Initial)
| Criterion | Threshold |
|-----------|-----------|
| Min Events | ≥ 500 labeled events (or justify) |
| Utility Uplift | ΔUtility ≥ +0.02 (absolute) |
| Recall Retention | Candidate Recall ≥ Baseline Recall - 0.01 |
| Precision Guard | Candidate Precision ≥ 0.60 (synthetic; adjust in prod) |
| FP Rate Ceiling | FPR ≤ 0.15 |
| Statistical Support | McNemar p ≤ 0.05 (or CI lower bound > 0) |

## Reproducibility
- Specify random seed; stored inside evaluation artifact (`config.seed`).
- Record dataset manifest hash (future: `events.manifest.json`).
- Capture detector configuration (window, stddev, runtime params) & environment commit hash.
- Avoid non-deterministic detectors unless they expose a seed.

## Data Integrity & Label Handling
- Labels consumed: `event.labels.is_anomaly` (boolean-like).
- Events lacking label default to negative (0) unless future `unknown` triage class introduced.
- Out-of-time evaluation segments recommended for drift assessment (future).

## Drift Monitoring Integration (Planned)
- Population Stability Index (PSI) per numeric feature between reference baseline distribution and current evaluation window.
- PSI Ranges: <0.1 stable, 0.1–0.25 moderate shift, >0.25 significant shift requiring investigation.
- Feature PSI exported as Prometheus gauge: `neuron_feature_psi{tenant,feature}` (pending implementation) enabling correlation with metric degradation.

## Anomaly Traceability (Planned)
- `/anomalies/trace?event_id=...` endpoint returns per-detector reasons & fusion decision path to support adjudication of disagreements revealed by McNemar test patterns.

## Limitations
- Synthetic events may not capture correlated multi-stage attack sequences.
- Label noise unmodeled; bootstrap CIs assume observed labels are ground truth.
- Current evaluation is event-level; feature-level anomaly quality not separately scored.

## Roadmap Extensions
- Calibration curves & Brier score for probabilistic detectors.
- Cost-sensitive utility variant with explicit incident handling cost model.
- Temporal stratified bootstrap for time-series autocorrelation mitigation.
- Multi-class extension (e.g., anomaly type taxonomy recall coverage).

## Usage Example
```
python scripts/evaluate_models.py events.jsonl --detectors baseline snn --bootstrap 1000 --seed 42 \
  --utility-weights 0.3 0.7 0.2
```
Produces `artifacts/eval/comparison_metrics.json`:
```
{
  "config": { ... },
  "detectors": { "baseline": {"f1": ..., "utility": ..., "f1_ci": [l,u], ... }, ... },
  "pairs": { "baseline_vs_snn": { "mcnemar": {"b":..,"c":..,"p_value":..}, "delta_f1": .. } }
}
```

## Governance Notes
- Store artifacts immutably under `artifacts/eval/` with timestamp naming for longitudinal tracking.
- Promotion decisions should cite exact artifact filename + commit hash.
- Record parameter changes influencing model behavior (already counted via `neuron_param_changes_total`).
