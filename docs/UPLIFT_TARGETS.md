# SNN Uplift Targets (Phase 3)

Purpose: Define quantitative success / stop criteria for enabling or de‑scoping the experimental SNN detector relative to the locked statistical baseline (Gate A08) so decisions are auditable and reproducible.

Applies To: Phase 3 (SNN Prototype) evaluation runs and any subsequent tuning cycles prior to Fusion (Phase 4).

## 1. Baseline Reference
Source Gate: A08 (Phase 2 Baseline Gate Closure)
Artifacts: `artifacts/eval/baseline_metrics.json`, `artifacts/eval/threshold_sweep.json`, Gate Report hash (see A08)
Key Snapshot Fields (for comparative normalization):
- baseline_precision
- baseline_recall
- baseline_f1
- baseline_anomalies_predicted
- baseline_threshold (governed param)

## 2. Target Metrics & Thresholds
| Metric | Definition | Target Band (Green) | Warning (Amber) | Fail (Red) | Control Tags |
|--------|------------|---------------------|-----------------|------------|--------------|
| Recall Uplift | (recall_snn - recall_baseline) / recall_baseline | ≥ +15% | +5% to <15% | < +5% | NIST SI-4, ISO A.8.16 |
| Precision Degradation | precision_baseline - precision_snn | ≤ 5% abs | >5% to 8% | >8% | SOC2 CC3.2 |
| F1 Uplift | f1_snn - f1_baseline | ≥ +10% | +3% to <10% | < +3% | NIST AU-6 (quality of info) |
| Added p95 Inference Latency | p95_latency_snn - p95_latency_baseline (ms) | < 5 ms | 5–8 ms | > 8 ms | ISO A.8.16 |
| CPU Overhead | (cpu_pct_with_snn - cpu_pct_baseline) | < 10% | 10–15% | >15% | NIST CP-2 (resilience) |
| Memory Overhead | ΔRSS MB | < 25 MB | 25–40 MB | >40 MB | ISO A.5.34 |
| Resource Guard Trigger Rate | guard_triggers / events | ≤0.5% | 0.5–1% | >1% | NIST SI-7 |
| Spike Density Band | Mean density (window) | 0.05–0.35 | 0.01–0.05 or 0.35–0.5 | <0.01 or >0.5 | NIST SI-4 |
| MTTR (SNN Recovery) | Time from guard disable to re-enable | <120s | 120–300s | >300s | ISO A.8.16 |
| Anomaly Overlap Ratio | |overlap| / |union| (baseline vs snn anomalies) | 0.4–0.75 | 0.2–0.4 or 0.75–0.85 | <0.2 or >0.85* | SOC2 CC7.x |

*Very high overlap (>0.85) with low recall uplift indicates lack of differentiated value.

## 3. Evaluation Procedure
1. Generate synthetic / replay dataset (seeded) feeding both detectors identically.
2. Collect raw anomaly decisions, timestamps, detector labels.
3. Compute per-detector TP/FP/FN using labeled events (or synthetic ground truth injection markers).
4. Emit `baseline_vs_snn_eval.json` with sections:
   - `baseline` (precision, recall, f1, anomalies)
   - `snn` (same fields + latency stats)
   - `delta` (uplifts & overhead)
   - `decision` ("proceed" | "tune" | "retire") derived from rules below.
5. Write hash of evaluation artifact to forthcoming gate report (A13 if proceeding).

## 4. Decision Logic
Pseudo:
```
if recall_uplift >= 0.15 and precision_loss <= 0.05 and latency_add_p95 < 5ms:
    decision = "proceed"
elif recall_uplift < 0.05 or precision_loss > 0.08 or latency_add_p95 > 8ms:
    decision = "retire_or_rethink"
else:
    decision = "tune"
```

## 5. Stop / Pivot Conditions
Immediately open a tuning or retirement review if any occur in two sequential evaluation cycles:
- Recall uplift Red OR Precision degradation Red OR Latency Red.
- Guard trigger rate Red OR spike density persistent out-of-band.

## 6. Audit & Governance
- Changes to targets require: audit entry referencing previous doc hash + reason (e.g., data domain shift).
- All evaluation artifact hashes appended to next gate report.
- Parameter changes between evaluation runs MUST be justified with rationale field (enforced by runtime param audit).

## 7. RAG / Knowledge Graph Tags
Tags: `uplift_targets`, `phase3`, `governance`, `metrics`, `decision_logic`
Node Links (planned):
- DETECTOR (snn) -> CONTROL (SI-4) via MONITORED_BY edge.
- EVAL_ARTIFACT -> UPLIFT_TARGETS (this doc hash) for traceability.

## 8. Future Extensions
- Adaptive threshold acceptance test (EWMA drift) integration.
- Confidence calibration scoring for fusion stage (Phase 4) referencing same baseline metrics.

## 9. Hashing & Integrity
This file’s SHA256 should be captured in the next gate report upon first use in evaluation.

---
Status: Draft v1 (to be referenced by Evaluation Report Generator script).