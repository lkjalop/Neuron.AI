# Neuron Platform Handbook

Status: Draft v0.1 (RAG-ready structure)
Audience: Executives, Analysts, Engineers, Investors

## 0. Navigation Map
| Section | Purpose | Tags |
|---------|---------|------|
| 1. Overview | What Neuron is & why | intro, strategy |
| 2. Phases Summary | Snapshot of phased roadmap | roadmap |
| 3. Architecture | High-level flow & modules | architecture |
| 4. Detection | Current & planned detectors | detection |
| 5. Metrics & KPIs | Operational + quality metrics | metrics, kpi |
| 6. Governance & Audit | Integrity & change control | governance |
| 7. Tuning Playbook | How to adjust thresholds safely | tuning |
| 8. Performance & Scale | Baselines & targets | performance |
| 9. Security Posture | Current controls & backlog | security |
| 10. Failsafes & Health | Degradation & recovery | failsafe |
| 11. Neuromorphic Path | SNN rationale & criteria | snn |
| 12. Fusion & Reasoning | Ensemble + explanation layer | fusion |
| 13. Response (Future) | Orchestration vision | response |
| 14. Data Export & ML | Dataset artifacts & usage | ml, export |
| 15. Glossary | Term definitions | glossary |
| 16. Change Log | Linking to audit log | audit |

## 1. Overview
Neuron is a governed anomaly detection platform with a phased approach: start with transparent statistical baselines; add neuromorphic experimentation only after measurable evidence of readiness; graduate to fusion and response layers while preserving auditability.

## 2. Phases Summary
| Phase | Theme | Gate Requirement (Simplified) |
|-------|-------|--------------------------------|
| 1 | Ingestion & Normalization | Stable multi-tenant event schema |
| 2 | Baseline Detection & Metrics | Evaluation + performance artifacts + gate report |
| 3 | SNN Shadow Prototype | Uplift vs baseline & resource cost within budget |
| 4 | Fusion & Reasoning | Calibrated confidence & drift monitoring |
| 5 | Response Orchestration | Safe-playbook dry-run track record |
| 6 | Executive Dashboard | KPI aggregation & explainability |

## 3. Architecture
Ingestion -> Queue -> Detectors (Baseline; SNN shadow in Phase 3) -> Fusion (Phase 4) -> Response (Phase 5) -> Dashboard (Phase 6). Cross-cutting: metrics, audit, param registry, failsafes.

## 4. Detection
- Baseline: rolling mean/std with MAD fallback per tenant/feature.
- Planned SNN: spike-based encoding (rate or latency) shadow mode initially.
- Future Fusion: weighted + calibrated ensemble.

## 5. Metrics & KPIs (Plain Language)
| Metric | Meaning | Owner |
|--------|---------|-------|
| Events Total | Volume processed | Platform |
| Anomalies Total | Count flagged unusual | Detection |
| Precision/Recall/F1 | Quality of detection | Detection Science |
| Processing Latency | Time to classify event | Platform |
| CPU / Memory | Resource consumption | Platform |
| Warm-Up Skips | Features still stabilizing | Detection |

## 6. Governance & Audit
- Canonical spec hash verified at startup.
- Audit log entries (Axx) map changes to rationale.
- Gate reports freeze an evidence snapshot (hash + metrics + params).

## 7. Tuning Playbook
1. Run threshold sweep script.
2. Compare F1 & precision trade-off.
3. Propose change with before/after metrics.
4. Update param via admin endpoint (future: auth) -> audit entry.

## 8. Performance & Scale
Baseline target: p95 processing latency < 100ms at synthetic load harness baseline. Resource guardrails: memory < 750MB, CPU < 70% sustained.

## 9. Security Posture
Current: metrics exposure (internal), static security scan, no external secrets stored. Backlog: RBAC for admin endpoints, signed artifacts, drift detection for model integrity.

## 10. Failsafes & Health
See `FAILSAFE_DESIGN.md` for layered matrix; health state exposed via summary endpoint (planned).

## 11. Neuromorphic Path
Adopt SNN only if uplift (F1 gain) exceeds operational complexity cost and resource overhead < defined budget. Shadow mode A/B logs used first.

## 12. Fusion & Reasoning
Ensemble blends baseline + SNN + rule heuristics; reasoning agent annotates context & confidence explanation; drift detectors guard weights.

## 13. Response (Future)
Playbooks run in dry-run first; circuit breakers prevent loops; progressive auth required for escalation levels.

## 14. Data Export & ML
Dataset export script produces JSONL anomalies + manifest (param snapshot) enabling reproducible ML experiments.

## 15. Glossary (Excerpt)
| Term | Definition |
|------|------------|
| Uplift | Improvement in a target metric vs baseline |
| Shadow Mode | Non-impacting parallel evaluation path |
| Gate Report | Evidence bundle for phase promotion |
| Drift | Distribution change undermining model validity |

## 16. Change Log
See `audit/AUDIT_LOG.md` (append-only).

## Appendix A: RAG Structuring Hints
- Each numbered section = independent embedding unit.
- Keep paragraphs short (< 120 words) for vector precision.
- Stable headers allow deterministic retrieval.

---
End of v0.1 Handbook.
