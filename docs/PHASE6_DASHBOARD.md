# Phase 6 Executive Dashboard Planning

Status: Draft (Pre-Implementation)
Scope Phase: 6 (post SNN + Fusion validation)
Owner: TBD

## 1. Purpose
Provide a single-pane executive + analyst view of detection health, anomaly quality, performance, resource usage, and governance posture. Emphasis on explainability, drift visibility, and parameter change traceability.

## 2. Personas & Goals
| Persona | Core Questions | Required Latency |
|---------|----------------|------------------|
| CISO / Exec | Are we improving detection quality? Any risk spikes? | Near real-time (< 30s) |
| SecOps Analyst | Which anomalies matter now? What changed recently? | Sub-10s for new anomalies |
| Platform Engineer | Are detectors healthy & performant? | 30–60s |
| Data Scientist (Phase 3+) | Is SNN contributing uplift vs baseline? | Periodic batch (5–10m) |

## 3. KPI Catalog
| KPI | Definition | Data Source | Update Cadence |
|-----|------------|-------------|----------------|
| Precision | TP / (TP + FP) | Evaluation artifacts | Daily / On-demand sweep |
| Recall | TP / (TP + FN) | Evaluation artifacts | Daily / On-demand sweep |
| F1 | Harmonic mean(P,R) | Evaluation artifacts | Daily |
| Anomaly Rate | anomalies_total / events_total | Live Prometheus | 1m scrape |
| Warm-Up Skip Rate | warmup_skips / events_total | Prometheus | 1m |
| MAD Fallback Rate | mad_fallback / events_total | Prometheus | 1m |
| Latency p95 | processing_latency_seconds{quantile=0.95} | Prometheus histogram | 1m |
| CPU / Memory | system gauges | Prometheus | 1m |
| Param Change Count | # changes last 24h | Param registry audit | 1h |
| Security Findings Open | High severity unresolved | Security scan artifacts | Daily |
| SNN Uplift (Phase 3+) | F1_snn - F1_baseline | Dual evaluation | Daily |
| Ensemble Confidence (Phase 4) | Avg calibrated confidence | Fusion module | 1m |

## 4. Data Sources & Access Layer
| Source | Access Method | Notes |
|--------|---------------|-------|
| Prometheus Metrics | /metrics scrape | Could add pushgateway for jobs |
| Evaluation Artifacts | artifacts/eval/*.json | Served via file API or object store |
| Gate Reports | artifacts/gate/*.json | Immutable evidence snapshots |
| Security Scan | artifacts/security/security_summary.json | Normalized JSON wrapper |
| Param Changes | runtime param audit log | Append-only, hashed segments |
| Anomaly Buffer | /anomalies | Timeout & pagination controls |

## 5. API Contract (Proposed New Endpoints)
| Endpoint | Method | Purpose | Auth Scope |
|----------|--------|---------|------------|
| /dashboard/summary | GET | Aggregated KPIs (rolling window) | exec_read |
| /dashboard/anomalies/top | GET | Top-N anomalies (score, recency) | analyst_read |
| /dashboard/drift | GET | Detector/SNN drift signals (psi, mean shift) | data_read |
| /dashboard/params/changes | GET | Recent parameter updates (24h) | exec_read |
| /dashboard/security | GET | Latest security scan digest | exec_read |
| /dashboard/uplift (Phase 3+) | GET | Baseline vs SNN metrics diff | data_read |
| /dashboard/fusion (Phase 4+) | GET | Ensemble contribution breakdown | data_read |

## 6. Architecture Sketch
1. Aggregator service polls artifacts & Prometheus (could stay inside core API initially).
2. Caching layer (in-memory) with TTL per data family.
3. Future: Move heavy aggregation (e.g., drift calculations) into async job queue.

## 7. Data Model (Summary DTO)
```json
{
  "timestamp": 1730000000,
  "kpis": {
    "precision": 0.91,
    "recall": 0.88,
    "f1": 0.895,
    "anomaly_rate": 0.012,
    "latency_p95_ms": 42.7,
    "warmup_skip_rate": 0.05,
    "mad_fallback_rate": 0.002,
    "cpu_percent": 14.2,
    "memory_mb": 210.4,
    "param_changes_24h": 1,
    "security_open_high": 0,
    "snn_uplift_f1": null
  },
  "notes": ["Latency within SLO", "No high severity vulns"]
}
```

## 8. Alerting & SLOs
| KPI | SLO / Threshold | Action |
|-----|-----------------|--------|
| Latency p95 | < 100ms | Investigate ingestion backlog > raise scaling gate |
| Anomaly Rate | 0.1%–5% window | Tune threshold if out-of-band |
| Precision | > 0.85 | Re-train or adjust feature set if below |
| Recall | > 0.80 | Add detectors / lower threshold |
| CPU Percent | < 70% sustained | Scale or optimize window sizes |
| Memory MB | < 750MB baseline | Profile SNN / window retention |

## 9. Security & Governance Integration
- Hash verification for canonical doc displayed.
- Param changes show diff + actor + reason.
- Signed artifact manifest (future) to detect tampering.

## 10. Iteration Plan
| Iteration | Deliverable | Success Metric |
|-----------|-------------|----------------|
| 1 | Summary endpoint + core KPIs | p95 < 100ms response |
| 2 | Anomaly list & param changes | Analyst feedback | 
| 3 | Drift panel + threshold banners | Early warning < 5m delay |
| 4 | SNN uplift view | Clear uplift or de-scope decision |
| 5 | Fusion contribution (Phase 4) | Explainability scoring |

## 11. Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| KPI sprawl | Cognitive overload | Strict catalog & review gate |
| Artifact drift | Inconsistent dashboards | Hash & timestamp freshness checks |
| Latency spikes | User mistrust | Cache & degrade gracefully |
| SNN complexity | Misinterpretation | Shadow mode + comparative diff |

## 12. Open Questions
- Do we expose raw anomaly payloads beyond buffer size? Need retention strategy.
- API pagination standardization (cursor vs offset) for anomalies.
- Where to store historical KPI time-series once Prometheus retention window expires? (Phase 7?)

## 13. Acceptance (Definition of Ready for Phase 6)
- All KPIs mapped to single authoritative source.
- Governance hooks (param/audit) accessible via endpoint.
- Performance target: summary endpoint under 150ms at 95th percentile baseline load.

---
Generated scaffold; update as phases progress.
