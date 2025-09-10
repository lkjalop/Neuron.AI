# SNN Testing & Validation Guide

This guide outlines how to begin validating the reservoir SNN scaffold and emergence probability model.

## Objectives
1. Confirm determinism (same seed => identical embeddings)\
2. Ensure stability (no NaNs, bounded state in [-1,1])\
3. Validate monotonic influence: larger input magnitude should increase reservoir energy (on average)\
4. Integration contract: embedding -> emergence probability influences risk_factors["emergence_p"].

## Suggested Property Tests (Hypothesis)
- Determinism:
  - Given identical config seed + identical window, `embed(window)` returns identical vectors.
- Bounded Activation:
  - For random windows, all state values satisfy `abs(v) <= 1.000001`.
- Energy Monotonicity (Probabilistic):
  - Construct two windows: W_low (values ~ N(0, 0.1)), W_high (values ~ N(0, 0.8)). Mean absolute value of embedding for W_high > W_low (allow tolerance). Repeat trials.

## Reservoir Energy Metric
A simple proxy: `energy = mean(abs(embedding))`. Feed into emergence model as `reservoir_energy`.

## Drift Score (Future)
Compute as: cosine_distance(embedding_t, embedding_{t-k}) or population variance across recent window of embeddings. Placeholder default = 0.0.

## Example Usage
```python
from predictive.reservoir import init_reservoir
from predictive.emergence import compute_emergence_probability

res = init_reservoir(size=64, sparsity=0.9, spectral_radius=0.85, leak=0.25, seed=42)
window = [[0.1, 0.0, -0.05]] * 20  # toy sequence
embedding = res.embed(window)
energy = sum(abs(x) for x in embedding) / len(embedding)
features = {
    "base_risk": 0.6,
    "epss": 0.2,
    "kev_listed": 0.0,
    "exploit_available": 0.0,
    "age_days": 15,
    "reservoir_energy": energy,
    "drift_score": 0.0,
    "feed_confidence": 0.95,
}
print("Emergence P=", compute_emergence_probability(features))
```

## CI Integration
- Add property tests gradually (start with determinism + bounded activation) to keep runtime low.
- Gate optional tests behind env var (e.g., `ENABLE_SNN_TESTS=1`).

## Future Enhancements
- Switch to `torch` tensors when GPU acceleration desired.
- Add spectral radius exact scaling via numpy eigenvalue approximation when numpy available.
- Track embedding variance to inform adaptive leak tuning.

## Risk Model Hook
During risk recompute:
1. Generate / retrieve feature window for asset-class vulnerability context (TBD data source).
2. Compute reservoir embedding & energy.
3. Compute emergence probability; store in `risk_factors["emergence_p"]`.
4. Optionally adjust composite risk score (e.g., `risk = max(risk, emergence_p * weight)`).

---
This document will evolve as predictive modules mature.
