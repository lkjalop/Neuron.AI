## Temporal Fusion Transformer (TFT) Integration Plan

Goal: Evolve current temporal detector (variance / attention / TFTLite) into a governed, auditable Temporal Fusion Transformer style module supplying a normalized contribution to fusion and enriched anomaly context.

### 1. Data Pipeline & Window Preparation
Inputs: Per-event numeric feature vector (ordered via `feature_order()`).
Pipeline steps:
1. Normalize (existing min/max normalization in `VectorSequenceBuffer`).
2. Maintain rolling window of length W (runtime param `snn.encoding_window` reused; introduce a dedicated `temporal.window` later).
3. Augment with positional encodings (sin/cos) + optional time-of-day & weekday scalars (add when timestamps available reliably).
4. (Future) Categorical covariates: derived event category / severity bucket.

Edge cases:
- Incomplete window: detector stays silent.
- High cardinality drift in features: fallback to variance path until calibration catches up.

### 2. Model Architecture (Phase Steps)
Phase A (current): Deterministic lightweight projection (TFTLite) for residual norm.
Phase B: Replace with PyTorch mini-transformer encoder layer stack (2–3 layers, d_model = F, n_heads = 4) + gated residual network (GRN) for feature importance approximation.
Phase C: Add static & known future inputs (if forecasting horizon introduced) with gating (skip if not available).
Phase D: Trainable parameter persistence (checkpoint to `artifacts/temporal/weights.pt`). Introduce signed manifest with hash chain.

### 3. Scoring & Calibration
Raw signals:
- Residual vector norm (prediction vs last vector).
- Mean variance across features (already computed for variance encoder).
- Attention deviation score (softmax similarity weighting path).

Unified score pipeline:
1. Compute per-encoder base score in [0, +).
2. Apply squashing (tanh) to map into (0,1).
3. Maintain per-tenant rolling quantiles (p50, p90, p99) using existing calibrator; expose p95 gauge approximation.
4. Fire anomaly when score >= dynamic threshold (p90 + margin) AND stability guards (variance > epsilon).
5. Store residual vector top-K contributions (abs residual) for context.

Runtime params (additions planned):
- `temporal.window` (int) specific window length (initially alias to `snn.encoding_window`).
- `temporal.encoder.mode` (enum: variance|attn|tft|auto).
- `temporal.anomaly.quantile` (float, default 0.9) calibrator quantile trigger.
- `temporal.anomaly.min_residual` (float) floor to avoid low-signal noise.
- `temporal.max_layers` (int) safety guard for deep transformer builds.
- `temporal.training.enable` (bool) allow fine-tuning.

### 4. Fusion Contribution
Compute normalized temporal contribution C_t:
    C_t = clamp(score / max(p90, eps), 0, 1)
Expose via metric `FUSION_TEMPORAL_CONTRIBUTION` and apply fusion weight param `detection.temporal.weight` inside arbitrator (future patch).

Adaptive tuner (existing tuner params) will sample (baseline_anoms, temporal_applied) windows and adjust weight toward target uplift ratio.

### 5. Persistence & State
Artifacts:
- Calibration JSON (already): extend schema with encoder mode version.
- Model weights (future PyTorch) under `artifacts/temporal/model_v{N}.pt`.
- Hash manifest appended to `audit/MANIFEST_CHAIN.jsonl` referencing SHA256 of weight file + params.

### 6. Metrics Expansion
- `TEMPORAL_MODEL_VERSION` (Gauge: version id numeric).
- `TEMPORAL_SCORE` (Histogram) for raw score distribution (per tenant) – optional to control cardinality.
- `TEMPORAL_TOP_FEATURE_RESIDUAL` (Counter with labels feature, bucket) limited cardinality (only top 3 features aggregated by hashed feature name prefix) to avoid blowup.

### 7. Resource & Safety Guards
- Max inference latency (existing `temporal.guard.max_latency_s`).
- Max residual variance (`temporal.guard.max_residual_var`).
- Add `temporal.guard.max_model_size_mb` (future when weights exist).
- Fallback path: on guard trip for 3 consecutive windows, drop to variance encoder until recovery.

### 8. Testing Strategy
Unit:
- Deterministic residual for synthetic linear ramp input.
- Encoder mode switching preserves anomaly firing semantics.
Calibration:
- Quantile estimator monotonic with added higher residual samples.
Integration:
- Fusion simple strategy sees temporal anomalies when enabled.
Regression:
- Guard triggers when artificial latency injected.

### 9. Incremental Delivery Plan
Release 1: Current consolidated file + param additions + fusion contribution (no PyTorch).
Release 2: Introduce PyTorch transformer (optional dependency) with weight hash audit.
Release 3: Adaptive tuner integration & persistence finalize.
Release 4: Feature attribution metrics & retrieval context expansion (store residual top features into corpus).

### 10. Open Questions / Future
- Horizon forecasting (multi-step) adds complexity; defer until anomaly semantics validated.
- Mixed frequency handling (irregular timestamps) – consider interpolation or masking.
- Compression of calibration history for memory footprint.

---
Document hash will be added to manifest after stabilization.
