# Pivot Decision: Lightweight Neuromorphic Scanner Path

Date: 2025-09-04
Status: APPROVED (Internal checkpoint / rally rollback point)
Owner: Platform R&D

## 1. Context
Original trajectory focused on an always-on hybrid detection pipeline (baseline + SNN + optional ISO Forest + fusion + governance). New strategic need: rapidly validate neuromorphic + hybrid detection value in *on-demand* (batch / episodic) scenarios that align with threat hunting, vulnerability assessment support, and forensic scans.

## 2. Why Pivot
| Driver | Explanation |
|--------|-------------|
| Time-to-Value | Faster to demonstrate neuromorphic uplift (accuracy / signal purity) via discrete scan artifacts than operating an always-on service. |
| Resource Efficiency | Removes need for continuous variance monitoring, queue depth metrics, real-time suppression gates while still preserving reproducibility. |
| Analyst Workflow Fit | Incoming internship tasks (threat hunts, ad-hoc investigations, vulnerability correlation) map better to triggered scans than passive monitoring. |
| Competitive Differentiation | Neuromorphic + temporal embeddings packaged as a focused “intelligence scan” differentiates from signature scanners. |
| Reversible | Existing orchestrator + detectors are reusable; streaming mode can be reinstated without re-architecture. |

## 3. Scope (Phase S0-S1)
IN SCOPE:
- `run_scan.py` CLI (batch events → anomalies + embeddings + insight report)
- Deterministic SNN + baseline comparison harness
- Temporal embedding builder (windowed feature summarization)
- Reproducibility (hash of anomaly log + embedding matrix)
- Minimal knowledge/ontology tagging (CVE/CWE sample mapping)
- History / manifest snapshot for rollback

OUT OF SCOPE (Deferred, not deleted):
- Continuous suppression / variance alerts
- Live adaptive tuner (optional; may freeze weights for scans)
- Long-lived ingestion queue metrics & backpressure handling
- Multi-tenant runtime separation (single scan context)
- Heavy fusion experimentation (kept as optional flag)

## 4. Success Criteria (Initial)
| Metric | Target |
|--------|--------|
| Re-run determinism (anomaly hash) | 100% identical on same dataset | 
| SNN vs Baseline anomaly separation (score distance) | > 20% uplift |
| False-positive proxy reduction (noise window rate) | >= 15% lower vs baseline |
| Embedding cluster purity (synthetic anomaly windows) | Silhouette > 0.55 |
| Analyst report generation time (10k events) | < 90s on dev workstation |

## 5. Artifact Outputs Per Scan
- `scan_report.json` (metadata, KPIs, hash digests)
- `anomalies.jsonl`
- `embeddings.npz` + `embeddings.meta.json`
- `insights.jsonl`
- `knowledge_tags.jsonl` (if ontology tagging enabled)
- `summary.md` (human narrative + tables)
- `param_snapshot.json`

## 6. Rollback / Rally Point
This document + updated manifest define a rollback anchor. To revert to pre-pivot continuous mode emphasis:
1. Re-enable reliability variance gating scripts in CI.
2. Reactivate tuner loop (precision + unique ratio) in deployment profile.
3. Reinstate Prometheus exporter service endpoints.
4. Reconfigure orchestration runner to streaming ingestion adapter.

## 7. Risk & Mitigations
| Risk | Mitigation |
|------|------------|
| Over-fitting to synthetic datasets | Add at least one real sanitized log bundle for shadow validation. |
| Loss of operational credibility | Preserve governance artifacts (hashes, param snapshots) in scan outputs. |
| Feature creep returns quickly | Stage gate: only after neuromorphic KPIs met proceed to more fusion complexity. |
| Analyst misinterpretation of neuromorphic metrics | Provide plain-language `NEUROMORPHIC_INTERPRETATION.md` (planned). |

## 8. Open Questions
- Do we need multi-language log tokenization early? (Tentatively NO – defer.)
- Will ontology ingestion require network fetch or rely on cached CVE snapshots? (Start cached.)
- Include lightweight embedding visualization (UMAP PNG) in Phase S1? (Optional if time.)

## 9. Immediate Next Implementation Steps (Proposed)
1. Add temporal embedding spec (`docs/TEMPORAL_EMBEDDING_SPEC.md`).
2. Implement `src/temporal/embedding_builder.py`.
3. Implement `scripts/run_scan.py` (core pipeline wrapper).
4. Add reproducibility checker (`--verify` re-run mode).
5. Add SNN vs baseline experiment script.
6. Seed knowledge ingestion stub + tagger.

## 10. Approval & Notes
Approved implicitly by product/engineering alignment conversation (2025-09-04). No destructive deletions performed; continuous runtime code remains dormant but intact.

---
*End of decision record – modifications require an appended AUDIT_LOG entry referencing this file.*
