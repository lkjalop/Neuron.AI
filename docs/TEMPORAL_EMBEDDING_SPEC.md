# Temporal Embedding Specification (Scanner / Streaming Hybrid)

Version: 0.1.0-draft (A20 pivot phase)
Status: Draft (not yet referenced by production code)  
Owner: Detection / Neuromorphic Working Track  
Related Artifacts: `scripts/experiment_neuromorphic_proof.py` (planned), `src/temporal/embedding_builder.py` (planned), `docs/SCANNER_PIVOT_DECISION.md`

## 1. Purpose
Provide a deterministic, reproducible representation of a recent event sequence (per tenant + channel) suitable for:
- Fusion weighting (temporal context features).
- Neuromorphic (SNN) separation analysis (activity vs baseline context).
- Forensic scanner batch mode (attach embedding hash to anomaly report for cross-run comparison & diffing).
- Future NLP / ontology enrichment (embedding metadata fields describe semantic slices: burst, periodicity, volatility).

## 2. Determinism Contract
Given the same ordered sequence of (timestamp, value) pairs and identical runtime params:
- Output MUST be byte-for-byte identical JSON (after canonical sorting) except for `generated_at` field (if included, exclude from hash) and version.
- Floating aggregates are rounded to 6 decimal places to avoid platform FP drift.
- Hash algorithm: SHA256 over canonical JSON string with keys sorted and excluding ephemeral fields.

## 3. Input Schema
```
sequence: List[Point]
Point: { "ts": float (epoch seconds), "value": float }
Constraints:
- Length >= 2 to compute rate-based features.
- Must be sorted by ts ascending prior to processing; builder will defensively sort though callers SHOULD pre-sort.
- Optional: if values contain NaN / inf they are dropped with a counter (nan_dropped).
```

## 4. Output Schema (JSON)
```
{
  "version": "0.1.0",
  "length": <int>,
  "window_seconds": <float>,          # ts_last - ts_first (rounded 6dp)
  "sampling.mean_dt": <float>,        # mean delta t (6dp)
  "sampling.jitter_coef": <float>,    # stdev(dt)/mean(dt) (6dp)
  "value.mean": <float>,
  "value.median": <float>,
  "value.std": <float>,
  "value.mad": <float>,               # median absolute deviation
  "value.min": <float>,
  "value.max": <float>,
  "value.p95": <float>,
  "value.iqr": <float>,               # Q3 - Q1
  "trend.slope_ols": <float>,         # simple OLS slope over (t,value)
  "trend.residual_std": <float>,
  "burst.count": <int>,               # segments where diff > burst_sigma * std
  "burst.total_magnitude": <float>,   # sum of abs(diff) above threshold
  "volatility.normalized": <float>,   # std / (abs(mean)+1e-9)
  "volatility.change_index": <float>, # mean(|diff|) / (abs(mean)+1e-9)
  "periodicity.autocorr_lag1": <float>,
  "periodicity.autocorr_lag2": <float>,
  "periodicity.energy_ratio": <float>,# (variance explained top freq) / total variance (FFT coarse)
  "stability.value_cv": <float>,      # coefficient of variation
  "stability.z_run_mean": <float>,    # mean absolute z-score run length
  "sparsity.non_zero_ratio": <float>,
  "density.positive_ratio": <float>,
  "nan_dropped": <int>,
  "hash": "<hex16>",                # first 16 hex chars of SHA256 canonical (excludes this field)
  "canonical_order": ["list","of","keys"], # for verification/debug
  "_meta": { "generated_at": <iso8601>, "builder_version": "0.1.0" }
}
```

## 5. Feature Derivation Details
- mean/median/std/mad/min/max/p95/IQR: standard statistical definitions (ddof=0). p95 via nearest-rank.
- OLS slope: slope of linear regression y = a + b * (t - t0). Use numerically stable two-pass sums.
- residual_std: std of residuals (value - (a + b * (t - t0))).
- burst detection: compute diff[i] = value[i] - value[i-1]; burst if |diff| > burst_sigma * std(diff) (burst_sigma default 2.5). Consecutive bursts counted individually; magnitude accumulates |diff|.
- volatility.normalized: std / (abs(mean)+1e-9).
- volatility.change_index: mean(|diff|) / (abs(mean)+1e-9).
- autocorr_lag{k}: Pearson correlation between series[:-k] and series[k:]. If variance zero -> 0.
- energy_ratio: coarse FFT using power spectrum; pick index (1..N/2) with max power; ratio = max_power / total_power (exclude DC component if N>1).
- value_cv: std / (abs(mean)+1e-9).
- z_run_mean: create z-scores (value - mean)/std (if std==0 -> all zeros). Count contiguous runs where |z| > z_threshold (default 1.5); average their lengths. If no runs -> 0.
- sparsity.non_zero_ratio: count(value != 0)/N.
- density.positive_ratio: count(value > 0)/N.

## 6. Parameters
Runtime configurable (with defaults for builder):
```
{
  "embedding.burst_sigma": 2.5,
  "embedding.z_run_threshold": 1.5,
  "embedding.min_length": 5,
  "embedding.enable_fft": true
}
```
If sequence length < min_length returns minimal embedding (length + hash only) with reason="too_short".

## 7. Hashing & Canonicalization
1. Build dict excluding `hash`.
2. Sort keys lexicographically; serialize with separators (',',':'), ensure floats formatted with '%.6f'.
3. Compute SHA256; store first 16 hex chars (full hash available if needed later).
4. Provide ordered key list in `canonical_order` for external verifiers.

## 8. Versioning & Backward Compatibility
- Increment patch when adding non-breaking keys.
- Increment minor when adding/removing keys or changing semantics; include migration notes.
- Major reserved for format overhaul (not expected during scanner MVP).

## 9. Error Handling
- On any numeric failure (overflow, fp error) set feature to null and continue; still included in canonical order with JSON null.
- If all primary stats null → mark embedding as degraded (add `_meta.degraded=true`).

## 10. Security / Governance
- No raw event payload persisted—only aggregated stats.
- Deterministic hashing enables tamper detection (recompute & compare).
- For forensic mode: store embedding JSON alongside anomaly report `anomaly_id.embedding.json` enabling offline diff.

## 11. Example (Illustrative)
```
{
  "version": "0.1.0",
  "length": 12,
  "window_seconds": 11.000000,
  "sampling.mean_dt": 1.000000,
  "sampling.jitter_coef": 0.000000,
  "value.mean": 2.916667,
  "value.median": 3.000000,
  "value.std": 1.284523,
  "value.mad": 1.000000,
  "value.min": 1.000000,
  "value.max": 5.000000,
  "value.p95": 5.000000,
  "value.iqr": 2.000000,
  "trend.slope_ols": 0.012345,
  "trend.residual_std": 1.250000,
  "burst.count": 1,
  "burst.total_magnitude": 3.000000,
  "volatility.normalized": 0.440000,
  "volatility.change_index": 0.380000,
  "periodicity.autocorr_lag1": 0.612345,
  "periodicity.autocorr_lag2": 0.412301,
  "periodicity.energy_ratio": 0.550000,
  "stability.value_cv": 0.440000,
  "stability.z_run_mean": 0.000000,
  "sparsity.non_zero_ratio": 1.000000,
  "density.positive_ratio": 1.000000,
  "nan_dropped": 0,
  "hash": "d3a4b6c81f9e2a10",
  "canonical_order": ["burst.count","burst.total_magnitude", "density.positive_ratio", "hash", ...],
  "_meta": { "generated_at": "2025-09-04T12:34:56Z", "builder_version": "0.1.0" }
}
```

## 12. Open Questions / Future Extensions
- Add rolling sub-window entropy features?
- Integrate categorical channel indicators (one-hot) as additional keys under `context.` namespace.
- Provide compression (zstd) for large embeddings (unlikely needed given small size <1KB).
- Inline anomaly alignment: annotate which indices correspond to anomaly timestamps for localized trend context.

## 13. Acceptance Criteria for Builder Implementation
- Unit test: identical input produces identical hash across 3 runs.
- Unit test: modifying one value changes hash.
- Unit test: sequence shorter than min_length returns minimal embedding structure with reason flag.
- Unit test: disabling FFT removes periodicity keys but keeps canonical order stable minus removed subset (hash changes + version micro bumped if removal enabled by param).

---
Prepared under pivot entry A20 to unblock embedding builder & neuromorphic proof harness.
