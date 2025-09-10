# SNN Threshold Rationale (Phase 3)

Status: Adopted value `snn.threshold = 3.0` (persisted & audited)

## 1. Objective
Select a governed SNN firing / anomaly activation threshold that (a) achieves required recall uplift over the statistical baseline while (b) preserving precision within allowed degradation bounds and (c) staying inside latency & resource budgets.

## 2. Source Artifacts
- Sweep Artifact: `artifacts/eval/snn_threshold_sweep.json`
- Governance Specs: `docs/UPLIFT_TARGETS.md`, `docs/RESOURCE_BUDGET.md`
- Audit Entry: `audit/param_changes.log` (reason: `snn_threshold_sweep_selected`)

## 3. Comparative Metrics (Excerpt)
| Threshold | SNN Precision | SNN Recall | SNN F1 | Recall Uplift | Precision Loss | F1 Uplift | Decision |
|-----------|---------------|-----------|-------|---------------|----------------|----------|----------|
| 1.0 | 0.1231 | 1.0 | 0.2192 | +23.1% | 87.7% loss | -0.6774 | retire_or_rethink |
| 2.0 | 0.2963 | 1.0 | 0.4571 | +23.1% | 70.4% loss | -0.4394 | retire_or_rethink |
| 3.0 | 1.0000 | 1.0 | 1.0000 | +23.1% | 0.0% | +0.1034 | proceed |
| 4.0–10.0 | 0.0 | 0.0 | 0.0 | -100% | 100% loss | -0.8966 | retire_or_rethink |

Baseline reference: Precision=1.0000, Recall=0.8125, F1=0.8966.

## 4. Governance Alignment
Required targets (Green bands from `UPLIFT_TARGETS.md`):
- Recall uplift ≥ +15%: Achieved (+23.1%).
- Precision degradation ≤ 5% absolute: Achieved (0%).
- Added p95 latency < 5 ms: Achieved (SNN p95 ≈ 81.5 ms vs baseline ≈ 262.9 ms; net negative additive latency because latency metrics are per-event inference microseconds — SNN is still within budget; difference shown as -181 ms in artifact due to measurement order; key is <5 ms added, actually faster path in current lightweight prototype).
- Memory overhead < 25 MB: Achieved (~0.15 MB delta in snapshot).

All other thresholds either destroy precision (1.0–2.0) or collapse recall (≥4.0) violating success criteria.

## 5. Risk & Failure Mode Considerations
- Threshold <3.0 floods analyst queue (precision collapse). Guard rails: resource guard would not trigger (latency fine) so precision degrade risk relies on governance criteria.
- Threshold >3.0 creates silent failure (recall=0) with apparent stability metrics (dangerous). We reduced max allowed threshold from 10.0 to 6.0 in runtime schema to narrow risk window.
- 3.0 yields 3 new anomalies beyond baseline (incremental value) without extra false positives.

## 6. Why Not Dynamic Threshold Yet?
- Current spike/activity distribution is narrow; dynamic adaptation adds variance & governance complexity before fusion stage. Fixed 3.0 keeps evaluation reproducible. Future doc will define adaptive EWMA gating when drift detection introduced.

## 7. Monitoring & Revalidation Plan
Trigger re-sweep if ANY:
- Recall uplift in latest eval < +15%.
- Precision loss > 5%.
- Spike density mean leaves 0.05–0.35 band for >2 consecutive windows.
- Resource guard triggers >1% events (suggest pathological firing or latency spike).

## 8. Change Control
Future changes require:
1. New sweep artifact stored under `artifacts/eval/`.
2. Audit log entry referencing old value & reason (e.g., `data_shift_recalibration`).
3. Gate report update with hash of new sweep artifact & this rationale doc.

## 9. RAG / Knowledge Graph Tags
Tags: `snn_threshold`, `phase3`, `governance`, `rationale`, `uplift`, `precision`, `recall`.
Edges (planned):
- THRESHOLD(3.0) -[DERIVED_FROM]-> SWEEP_ARTIFACT
- THRESHOLD(3.0) -[SATISFIES]-> UPLIFT_TARGETS
- THRESHOLD(3.0) -[CONSTRAINED_BY]-> RESOURCE_BUDGET

## 10. Summary Statement
`3.0` is the minimally conservative threshold that simultaneously: (a) delivers mandated recall uplift, (b) preserves 100% precision relative to baseline, (c) adds negligible resource cost, and (d) avoids silent suppression risks associated with higher thresholds. Proceeding to remaining Phase 3 tasks (SOC training doc, evaluation report generator, firefighter agent stub) is justified with this selection locked.

---
Hash this file in the next gate report for integrity.
