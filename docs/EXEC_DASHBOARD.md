# Executive Dashboard Specification

## Purpose
Provide leadership with governed Key Performance Indicators (KPIs) covering detection effectiveness, innovation contribution (SNN), operational efficiency, and governance safety for the Neuron AI XDR fusion platform.

## KPI Categories
| Category | KPI | Source Metric / Derivation | Governance Signal |
|----------|-----|----------------------------|-------------------|
| Fusion Effectiveness | Overlap Ratio | neuron_fusion_overlap_ratio | Detector drift if falling |
| Fusion Effectiveness | SNN Unique Ratio (rolling) | neuron_fusion_snn_unique_ratio_rolling | SNN novelty/coverage |
| Governance | Suppression Rate | neuron_fusion_suppression_rate | Over-suppression risk |
| Governance | Suppression Alerts | neuron_fusion_suppression_alerts_total | Policy breach count |
| Contribution | Baseline vs SNN Volume | Counters from detectors | Detector balance |
| Quality Proxy | Precision Proxy | Rolling SNN unique ratio vs union | Alert noise watch |
| Operations | Event Throughput | neuron_pipeline_events_total / time | Scaling adequacy |
| Operations | Detector Latency p95 | neuron_detector_latency_seconds | Performance regressions |
| Operations | Queue Depth | neuron_ingestion_queue_depth | Backpressure early warning |
| Resources | Memory / CPU | process metrics (psutil + custom) | Capacity planning |
| Governance | Param Change Velocity | neuron_param_changes_total delta | Change control adherence |
| Safety | Integrity Hash Status | Compare canonical doc hash | Tamper detection |
| Resilience | Guard Trips | neuron_resource_guard_trips_total | Stress / DOS defense |

## JSON Endpoint Design
Endpoint: `/executive/kpis` (admin protected)
```
{
  "timestamp": 1730000000,
  "fusion": {"overlap_ratio": 0.42, "snn_unique_ratio_rolling": 0.18, "suppression_rate": 0.07, "suppression_alerts": 1},
  "detection": {"baseline_anomalies": 120, "snn_anomalies": 95},
  "operations": {"events_per_sec": 52.3, "detector_latency_p95_ms": {"baseline": 3.5, "snn": 7.2}, "queue_depth": 0},
  "resources": {"memory_mb": 210.4, "cpu_percent": 34.1},
  "governance": {"param_changes_24h": 2, "integrity_hash_ok": true, "guard_trips": {"rate_limit":0}},
  "flags": {"suppression_overrun": false, "overlap_drop": false}
}
```

## Aggregation Mechanics
1. Collect raw Prometheus metrics from internal registry.
2. Maintain rolling minute buckets in-memory (ring buffer length configurable, default 60) for sparkline generation.
3. Compute derived KPIs on request to keep endpoint light.

## Thresholds & Color Logic
| KPI | Green | Yellow | Red |
|-----|-------|--------|-----|
| Suppression Rate | <= alert_threshold * 0.8 | <= alert_threshold | > alert_threshold |
| Overlap Ratio | >= historical_mean*0.9 | >= historical_mean*0.75 | < historical_mean*0.75 |
| Detector Latency p95 | <= SLO | <= 1.25x SLO | >1.25x SLO |
| Queue Depth | 0-5 | 6-20 | >20 |

## Auto-Fallback Logic (Phase 5)
If suppression_rate exceeds alert threshold for K consecutive windows, emit audit entry and set `detection.fusion.strategy` to `pass_through` until manual review.

## RAG / Knowledge Base Integration
Documents prioritized: this spec, `PHASE4_FUSION_ROADMAP.md`, `SOC_ANALYST_GUIDE.md`, `THREAT_MODEL.md`, `SNN_THRESHOLD_RATIONALE.md`. Index with semantic embeddings; attach doc hash to detect tampering.

## Implementation Steps
1. Add metrics (throughput, latency, queue depth, param change, guard trips).
2. Implement `ExecutiveAggregator` maintaining ring buffers.
3. Add `/executive/kpis` endpoint and admin auth.
4. Add auto-fallback suppression guard.
5. Add tests: endpoint shape, latency histogram presence, fallback trigger.
6. Extend gate report to optionally embed KPI snapshot.

## Security Considerations
- Endpoint guarded by admin token/HMAC.
- No raw event payloads; only aggregates.
- Redact tenant-specific sensitive data if multi-tenant exposure risk (optionally provide per-tenant restricted view).

---
This spec will evolve with feedback from leadership and SOC operations.