# SNN Encoding & Anomaly Scoring Design (Phase 3/4 Evolution)

Status: UPDATED (Encoder V2 + Residual, Pre-A12)  
Related Parameters: `detection.enable_snn`, `snn.encoding_window`, `snn.rate_scale`, `snn.lif_decay`, `snn.threshold`, `snn.encoder`, `snn.encoder.rate_v2.global_shrink`, `snn.encoder.rate_v2.min_floor`, `snn.encoder.rate_v2.debug`, `snn.encoder.rate_v2.debug_no_cap`, `seq.forecaster.enable`  
Related Controls (mapping preview): NIST 800-53 SI-4 (Monitoring), SI-10 (Information Input Validation), CM-3 (Configuration Change), AU-12 (Audit Generation); ISO 27001:2022 Annex A: A.5.7, A.8.16, A.8.28, A.8.30; SOC 2: CC7.2, CC7.3; ISO/IEC 42001 (draft alignment): Transparency, Robustness, Human Oversight.

---
## 1. Objectives
Introduce a neuromorphic (spiking) detector operating alongside the baseline statistical detector to:
- Capture temporal micro-patterns lost in simple rolling mean/variance.
- Provide robustness via ensemble (statistical + spiking). 
- Maintain auditability and deterministic reproducibility for the encoding stage.

Constraints:
- Deterministic given fixed params and input sequence order.
- Bounded resource usage: O(F * T) memory where F = number of numeric features, T = `snn.encoding_window`.
- Graceful disable (flag off or dependency missing) without affecting baseline path.

## 2. Data Path Overview
```
Event.features (numeric subset) --> Feature Vector v (length F) --> Normalization --> Rate Allocation --> Spike Tensor S shape [T, F]
                                --> LIF Network (snntorch) --> Output Activity (A) --> Score --> DetectionResult (if anomalous)
```

## 3. Feature Selection & Ordering
All numeric (int/float) features from `event.features` are selected. Order is stable via sorting by key to ensure deterministic mapping (important for test hashing and reproducibility). Non-numeric are ignored.

```
keys = sorted(k for k,v in features.items() if isinstance(v,(int,float)))
vector = [float(features[k]) for k in keys]
```

## 4. Normalization Strategy (V1 vs V2)
Goal: Scale heterogeneous feature magnitudes to comparable ranges for rate coding.
Approach (Phase 3 initial - RateEncoderV1):
1. Per-feature rolling min/max not maintained yet (would add state). For simplicity and transparency we apply a bounded tanh scaling after optional global standardization fallback.
2. Compute simple global magnitude reference: m = max(1e-9, median(|v_i|) + MAD(|v_i|)) using same median/MAD helpers as baseline logic (no cross-state coupling yet).
3. Normalized value: `n_i = tanh(v_i / (m * 3))` ∈ (-1,1). Negative values handled by optional rectification (Version 1: take abs for spike rate while preserving sign separately if needed later). For V1 anomaly scoring we ignore sign.

Rationale: Avoid dependence on long-term feature distributions until we define persistent state & drift handling; keeps encoding stateless except for parameter set.

### 4.1 Enhancements in RateEncoderV2
Encoder V2 introduces a more contrastive scaling path to better emphasize bursts while keeping global uplift within governed bounds.

Pipeline (per event):
1. Extract magnitudes `m_i = |v_i|` for numeric features.
2. Robust reference: `med = median(m_i)`; robust dispersion surrogate: `mad = median(|m_i - med|)` (fallback 1.0 if 0 to avoid divide-by-zero).
3. Reference composite: `ref = med + mad` (acts as soft scale anchor and implicit burst detector baseline).
4. Pre-shrink rate proposal: `r_i = (m_i + eps) / (ref + eps)`; optional burst emphasis: if `m_i > med + k * mad` apply multiplicative boost (current constants: `k≈3`, `boost≈1.8`).
5. Global shrink: `r_i *= global_shrink` (configurable) to coarsely position uplift band.
6. Floor: apply `min_floor` AFTER shrink to prevent total silencing of small but informative features. Effective floor is max(`min_floor`, `1/encoding_window`) to guarantee at most one spike path viability over a window for any non-zero magnitude if other scales are extreme.
7. Density cap: sum projected spikes over window `T` as `Σ(r_i * T)`; if implied active fraction exceeds cap (default 0.35) uniformly scale all `r_i` by a factor so that resulting projected active density hits the cap. This produces graceful global compression instead of harsh per-feature clipping.
8. Deterministic accumulation (Section 5) generates spike train.

Design Rationale:
- `med+mad` stabilizes scale against single large outlier (vs pure max).
- Burst gating provides selective boost so true bursty deviations rise above background without inflating all rates.
- Global shrink separates coarse uplift positioning from local contrast handling: tuning shrink moves entire uplift curve smoothly (monotonic relation tested empirically).
- Density cap enforces guardrail on compute & false positive explosion risk; uniform scaling preserves relative ordering across features.
- Floor ensures “rare but real” low-magnitude dimensions are never permanently zeroed by shrink—supporting anomaly diversity.

Debug Controls:
- `snn.encoder.rate_v2.debug`: emits per-event diagnostics: mags, med, mad, ref, pre-shrink vector, post-shrink+floor vector, projected spike count, density.
- `snn.encoder.rate_v2.debug_no_cap`: bypasses density cap to analyze unconstrained excitation (NEVER enable in production).

Failure Handling & Fallbacks:
- If all magnitudes zero → direct zero spike vector (no division churn).
- If `mad`=0 → set `mad=1.0` to revert to median-only scaling avoiding singularity.
- If after shrink all rates fall below floor → floor restoration ensures minimal sparse spike pattern to keep activity estimator alive.

Observed Tuning Pattern (empirical): uplift scales roughly linearly with `rate_scale * global_shrink` in moderate ranges; density cap introduces soft saturation beyond target.

## 5. Rate Coding (Temporal Expansion)
Given normalized magnitude `u_i = |n_i|` ∈ [0,1):
```
base_rate_i = clamp(u_i * rate_scale, 0, rate_scale)
T = snn.encoding_window (time steps)
Expected spikes per feature over window ≈ base_rate_i * T
Deterministic spike generation: threshold accumulation method

acc_i = 0
for t in 0..T-1:
    acc_i += base_rate_i
    if acc_i >= 1:
        emit spike S[t,i] = 1; acc_i -= 1
    else:
        S[t,i] = 0
```
This produces a near-uniformly distributed spike pattern (no RNG) whose spike count equals floor(base_rate_i * T) or floor/ceil by ≤1 rounding error. Determinism facilitates hashing tests. A tiny epsilon (1e-9) is added during accumulation comparisons to mitigate pathological floating remainder stalling.

### 5.1 Spike Density & Energy
We log:
- Per-event spike density = active spikes / (F * T).
- Spike energy (aggregate for session) = sum of per-event spike counts (diagnostic uplift proxy).

Density is bounded via encoder’s cap; guard layer can still override if multi-event rolling density breaches `snn.guard.max_spike_density`.

## 6. LIF Network (Prototype)
Minimal architecture (Phase 3 prototype):
```
Input dimension: F
Layer 1: LIF (snntorch Leaky) size H (e.g., H=F) with decay = snn.lif_decay
Readout: Sum of spikes over window (or last membrane potential) -> scalar activity A
Score: score = max(0, A - snn.threshold)
```
If score > 0 -> produce anomaly record containing: feature_vector_hash, spikes_sum, activity, score.

Future extensions:
- Multi-layer with dropout-like regularization via noise injection (governed).
- Adaptive threshold from rolling statistics of A.

## 7. Determinism & Seeding
- No randomness in encoding.
- LIF network uses default initialization; to stabilize reproducibility we will seed torch (if present) with fixed constant on module load (`torch.manual_seed(1337)`). Documented for audit.

## 8. Resource Constraints & Monitoring
Metrics (planned):
- `snn_inference_latency_seconds` (Histogram)
- `snn_spike_rate` (Gauge or Summary) = total_spikes / (F*T)
- `snn_anomalies_total` (Counter)

Potential guard: If average latency over last N windows > threshold (config TBD) trigger automatic disable (failover state machine, later task).

## 9. Security & Compliance Linkage (Preview)
| Design Element | Control Link (Examples) | Rationale |
|----------------|--------------------------|-----------|
| Deterministic encoding & param governance | NIST CM-3 / ISO A.8.32 / SOC2 CC8.1 | Controlled configuration changes |
| Audit of enable flag (A12 gate) | NIST AU-12 / ISO A.5.7 | Trace enabling advanced model |
| Integrity hash of docs + design presence | NIST SI-7 / ISO A.8.16 | Detect unauthorized design drift |
| Dual detector ensemble | NIST SI-4 / ISO A.8.28 | Enhanced monitoring coverage |
| Latency guard & disable path | NIST CP-10 (resilience), SOC2 CC7.2 | Prevent resource exhaustion impact |
| Normalization bounds and clipping | NIST SI-10 | Input validation & robustness |

(Full mapping to be expanded in `COMPLIANCE_MAP.md`).

## 10. Edge Cases & Failure Modes
| Case | Handling | Notes |
|------|----------|-------|
| All features non-numeric | No spikes (empty vector) -> no SNN processing | Safe skip |
| Extremely large values | tanh scaling bounds to <1 | Prevent overflow |
| Negative values | Magnitude only (abs) used for rate; sign ignored | Future: polarity channels |
| T=0 or <1 | Guard: enforce min=1 via schema | Already validated in params |
| rate_scale very high | Clamped per-step spike emission bounded by T + density cap scaling | Avoid explosion |
| global_shrink too small (≈0.01) | Effective floor still emits minimal spikes | Prevent dead model |
| density cap disabled (debug) | Potential spike flood; rely on guard or manual testing only | Not for production |
| Missing torch/snntorch | Graceful skip; baseline only | Logged warning |

## 11. Testing Strategy Alignment
Planned tests (referenced by todo IDs):
- Deterministic encoding hash (14)
- Monotonicity (15)
- Fallback without torch (16)
- Resource guard (17)
- Adversarial saturation & noise (18, 28)

## 12. Residual Sequence Forecaster (Experimental Add-On)
When `seq.forecaster.enable` is true a lightweight sequence buffer maintains the last N activities and a stub “forecaster” estimates expected activity; positive residual (actual - forecast) is passed through `tanh` and added as an auxiliary activity boost (bounded). This gently elevates anomalies during sudden upward shifts not yet internalized by baseline scaling. Residual contribution is separately metered so its risk can be audited.

Safeguards:
- Only positive residual contributes (no suppression on negative miss).
- Contribution bounded (-1,1) then scaled << main pathway.
- Easily disabled at runtime.

## 13. Tuning Guidelines (Observed)
Goal uplift band: 2.0–3.5× baseline anomalies.

Procedure:
1. Set `global_shrink` moderately (0.3–0.5) and pick base `rate_scale` near 1.0.
2. Sweep `rate_scale` in small increments (±0.02) measuring uplift & spike density.
3. If uplift >> target, first decrease `rate_scale`; if still high lower `global_shrink` (coarser lever).
4. If uplift < target raise `rate_scale` slightly; only raise `global_shrink` if already near saturation (density frequently at cap).
5. Keep `min_floor` at ~0.05 unless model becomes noisy—then reduce carefully (risk: silent suppression).

Recommended Production Starting Point (current empirical set): `rate_scale≈1.03`, `global_shrink=0.4`, `min_floor=0.05` yielding uplift ~2.5–3.1× with density < 0.3 in synthetic multi-pattern blend.

## 14. Future Enhancements (Out of Scope for Current Iteration)
- Adaptive rate via rolling feature variance.
- Spike-timing dependent plasticity (STDP) for threshold adaptation.
- Ensemble weighting & score fusion rationale document.
- Per-tenant personalization.

## 15. Implementation Roadmap Linkage
1. (Current) Design doc committed.
2. SNN Detector scaffold constructs deterministic encoder & placeholder score.
3. Add LIF layer & metrics.
4. Add tests + compliance mapping updates.
5. Gate A12 after evidence generation.

---
Document Hash Note: This file will be included in future canonical integrity set when SNN moves from experimental to governed (pending update to `CANONICAL_DOC_HASH`).
