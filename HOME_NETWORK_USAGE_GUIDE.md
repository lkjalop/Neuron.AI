# Home Network Usage & Validation Guide

## Purpose
Turn the platform + graph notebook into a mini-SIEM for a home / lab network to practice threat hunting, anomaly detection, and contextual triage.

## Why This Approach Works
| Capability | Value | Why vs. Simpler Approach | Trade-offs |
|------------|-------|--------------------------|------------|
| In-memory Relationship Graph | Fast iteration, contextual pivots | Rich multi-entity context vs. flat logs | Volatile, memory-bound |
| Embeddings (Node2Vec-lite) | Similarity & cluster discovery | Captures structural nuance beyond degree | Requires retraining; interpretability |
| Feature Fusion (stats + embedding) | Higher anomaly precision | Combines behavioral + structural signals | Increased complexity, tuning |
| Dual Anomaly Scoring (IF + distance) | Robust to single-model bias | Two orthogonal rarity views | More compute per cycle |
| Threshold Calibration | Controlled FP rate | Explicit performance target | Needs periodic refresh |
| TTL Pruning | Reduces noise & drift | Avoids stale IOC pollution | Risk of pruning rare true events |
| Auth Microservice | Secure remote queries | Prevents unchecked data exfil | Secret mgmt overhead |

## Architecture Flow (Home Lab)
1. Collect flows (router export, Zeek/Bro, dnsmasq logs, firewall logs) -> parse to canonical flow schema.
2. Normalize & classify (service buckets, direction, temporal features).
3. Update graph (devices ↔ IPs ↔ domains/IOCs) with rolling aggregation.
4. Periodically (or on-demand) regenerate embeddings + features.
5. Run anomaly scoring pipeline; log top-N changes over time.
6. Query microservice (`/graph/nodes`, `/graph/neighbor/{id}`, `/graph/anomalies/top`) for investigation.
7. Apply calibration threshold to decide which anomalies escalate (manual review vs. alert channel stub).

## Data Ingestion Options
| Source | Method | Notes |
|--------|--------|-------|
| Router syslog | Remote syslog to local collector; tail and parse | Filter only connection allow/deny lines |
| Zeek (recommended) | `conn.log` -> JSON parse -> flows_df | Rich fields like duration, orig_bytes, resp_bytes |
| Suricata | EVE JSON -> treat alerts as high-weight edges | Map signature to synthetic IOC nodes |
| Passive DNS | Periodic dump -> domain ↔ IP edges | TTL aging can feed pruning heuristics |
| Endpoint (EDR-lite) | Script enumerating outbound sockets | Use as supplementary enrichment |

## Step-by-Step Home Lab Quick Start
1. Clone repo & run core API (optional if only using notebook).
2. Open `notebooks/home_lab_graph_siem.ipynb` and execute sections 1–12 for baseline model; then 13–18 for streaming behavior.
3. Replace simulation in Section 3 with real log loader (write adapter returning list[dict]).
4. Tune anomaly calibration in Section 12 after ~24h of real data for stable baseline.
5. Set environment variables:
   ```bash
   export GRAPH_API_KEY=your_long_random_key
   export GRAPH_FEATURE_REFRESH_SEC=120
   export GRAPH_NODE_TTL_SEC=7200   # 2h TTL for transient IOCs
   ```
6. Enable microservice and query anomalies:
   ```bash
   curl -H "X-Graph-Key: your_long_random_key" http://localhost:8000/api/v1/graph/anomalies?top_k=10
   ```
7. Investigate suspicious nodes: pivot neighbors → correlate with endpoints / DNS logs.

## Validation Plan
| Goal | Validation Action | Success Criteria |
|------|-------------------|------------------|
| Data Integrity | Schema assert (non-null core fields) | 0 schema assertion failures |
| Embedding Health | Variance > 0.000001 | Pass variance assertion |
| Anomaly Distribution | Stddev(score_fused) > 0 | Non-zero stddev |
| Threshold Calibration | Synthetic recall > 0.8 at FPR < 0.15 | Achieved in Section 12 sweep |
| Pruning Efficacy | Node count reduction after TTL pass | Stale nodes removed (>0 if stale present) |
| API Security | 401 on bad token; 200 on correct | Both outcomes observed |
| CI Coverage | `pytest -k graph` passes | Green subset run |

## Hunting Playbook Examples
### Suspicious Beaconing Domain
1. Identify node with high `activity_1h` vs `activity_24h` baseline.
2. Check neighbors; if small stable set of external IPs, possible C2 beacon.
3. Manually enrich domain via whois / passive DNS.

### Lateral Movement Candidate
1. High unique_peers for an internal device + spike in port_diversity.
2. Use NN to see if embedding neighbors are mostly external (unexpected for workstation).
3. Examine raw flows during spike interval (filter by hour).

### Potential Exfiltration
1. Node with large `total_bytes` increase and elevated `mean_bytes_per_flow`.
2. Score above threshold and unusual embedding cluster shift.
3. Validate by checking destination ASN or geo (extend schema if needed).

## Scaling & Hardening Roadmap
| Phase | Upgrade | Benefit |
|-------|---------|---------|
| Short-Term | Replace manual walks with tuned Node2Vec / gensim full | Better structural capture |
| Short-Term | Add edge-type weighting | Improve semantic resolution |
| Mid-Term | Temporal decay weighting in features | Reduce stale bias |
| Mid-Term | Prometheus metrics export | Ops visibility |
| Mid-Term | Persistence layer (SQLite/Postgres) | Restart resilience |
| Long-Term | Switch to PyG + GraphSAGE | True learned generalization |
| Long-Term | Active learning (feedback labels) | Precision improvement |

## Risk & Mitigation
| Risk | Impact | Mitigation |
|------|--------|-----------|
| Over-pruning TTL | Miss rare stealthy indicators | Set conservative TTL, audit removals |
| Embedding Drift | Threshold invalidation | Periodic recalibration, track score distribution |
| False Positives | Alert fatigue | Multi-signal fusion, raise threshold gradually |
| Single Host Compromise | Graph misleads (poisoned edges) | Integrity checks, edge type anomaly heuristics |

## Glossary
- **Fusion Score**: Combined anomaly representation blending structural and embedding rarity.
- **TTL Pruning**: Time-based removal of stale nodes to maintain a responsive active topology.
- **Calibration**: Empirical threshold selection balancing recall & false positive rate.

---
**Next Steps:** Add continuous metrics, real ingest adapters, and integrate the anomaly output with a notification channel (Slack/webhook) gated by threshold + suppression rules.
