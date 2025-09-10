# SOC Analyst Guide: Neuron AI Fusion & XDR Platform

Audience: Non-technical Security Operations Center (SOC) analysts.

## 1. What the Platform Does (Plain Language)
Neuron AI ingests security-relevant event signals (resource usage, behavioral indicators, etc.) and uses two anomaly detectors:
- Baseline Detector: Learns typical behavior ("what normal looks like") using rolling statistics.
- SNN (Spiking Neural Network) Prototype: An experimental detector that encodes event features as spikes and fires when patterns deviate from learned temporal structure.

The Fusion Layer combines their outputs into final anomaly alerts using a selected strategy. Governance metrics watch for unhealthy suppression (hiding alerts) or drift (detectors disagreeing too much).

## 2. Core Components (Agents)
| Component | Role | What To Look For |
|-----------|------|------------------|
| Baseline Detector | Stable statistical anomaly detection | Sudden drop in anomalies may mean threshold too high |
| SNN Detector | Finds novel/complex patterns | Surge in unique SNN anomalies: investigate new behavior or noise |
| Fusion Arbitrator | Chooses final anomalies and may suppress duplicates | Rising suppression rate -> potential loss of coverage |
| Suppression Buffer | Stores recently suppressed anomalies for review | Repeated suppressed anomalies from same source may indicate mis-weighted strategy |
| Runtime Param Registry | Central live-tunable settings (strategy, thresholds) | Unauthorized or unexpected changes |
| Metrics Exporter | Provides Prometheus-format operational & fusion metrics | Missing metrics may mean service issue |
| KPI Endpoint (Phase 5) | Executive summary JSON for dashboards | Red flags / color changes |
| Audit Trail | Immutable log of changes and key events | Gaps or tampering attempts |

## 3. Fusion Strategies (When to Use)
- pass_through: Exploration / broad detection (higher noise).
- baseline_priority: Reduce duplicates, keep baseline trust. Recommended default.
- consensus_only: Use when high precision is mandatory and missing some anomalies is acceptable (e.g., strict gating). Monitor suppression rate closely.

## 4. Key Metrics (Interpretation)
| Metric | Normal Range | Action if Out of Range |
|--------|--------------|-----------------------|
| Overlap Ratio | Stable or gently trending | Investigate detector drift if sharp drop |
| SNN Unique Ratio | Some non-zero contribution | If zero -> SNN silent / disabled / misconfigured |
| Suppression Rate | Below configured alert threshold | If above -> consider switching strategy or threshold tuning |
| Suppression Alerts Total | Low / stable | Spike -> governance review |
| Detector Latency (p95) | Within SLO (to be defined) | High -> performance regression |
| Param Change Velocity | Low, deliberate | Unexpected burst -> potential misuse |

## 5. Common Anomaly Patterns & Analyst Actions
| Pattern | Possible Cause | Action |
|--------|----------------|-------|
| Burst of SNN-only anomalies | New workload / data drift | Validate with baseline context, consider threshold recalibration |
| Suppression rate climbing | Over-aggressive strategy | Examine suppressed buffer; maybe revert to pass_through |
| Overlap ratio collapsing | Detector divergence / broken SNN | Check SNN logs & performance, consider retrain/disable |
| Zero anomalies overall | Input pipeline stalled | Verify ingestion health & queue depth |

## 6. Threat / Attack Indicators Monitored
- Resource spikes (CPU/Mem) suggest possible abuse or lateral move tools.
- Unusual pattern sequences detected by SNN may indicate staged multi-step activity.
- Parameter tampering attempts (frequent unauthorized changes) flagged in audit.
- Over-suppression attack (attempt to hide anomalies) detected via suppression rate alerts.

## 7. How To Review Suppressed Anomalies
1. Call admin endpoint `/fusion/suppressed` (secure access) to list recent suppressed items.
2. Look for repeated entities or detectors always suppressed.
3. If critical anomalies suppressed, adjust strategy or thresholds.

## 8. Demo Playbook
| Step | Action | Expected Observation |
|------|--------|----------------------|
| 1 | Start service & generate synthetic events | Baseline anomalies appear after warmup |
| 2 | Switch to `baseline_priority` | SNN-only duplicates suppressed (suppression rate > 0) |
| 3 | Introduce extreme events | Both detectors fire; overlap ratio stable |
| 4 | Switch to `consensus_only` | Only joint anomalies; suppression rate increases |
| 5 | Query /metrics | Observe counters/gauges update |
| 6 | Generate gate report with `--metrics-url` | Fusion & suppression table included |
| 7 | Review suppression buffer endpoint | Recently suppressed anomalies listed |

## 9. FAQs
Q: Why are some SNN anomalies suppressed?  
A: Current strategy prioritizes baseline for de-duplication; SNN contribution still tracked.

Q: What triggers a suppression alert?  
A: Suppression rate exceeding configurable `fusion.suppression_alert_rate` rolling threshold.

Q: How do I know if documentation was tampered with?  
A: Gate report includes canonical doc hash; mismatch raises integrity concern.

## 10. Escalation Workflow
1. Anomaly flagged (or suppression alert raised).
2. Validate context (tenant, time, feature spikes).
3. Check suppression buffer (ensure not discarding high-risk patterns).
4. File incident entry (future incident module) or escalate to engineering if systemic.

## 11. Glossary
- Overlap Ratio: % of anomaly decisions agreed by both detectors.
- Unique Ratio: % of anomalies produced by only one detector.
- Suppression: Removal of a detector output from the final alert set due to strategy rules.
- Rolling Window: Recent N decisions used for dynamic rate calculations.
- Temporal Buffer: A short rolling history of normalized feature snapshots used to detect evolving patterns (e.g., gradual ramps, coordinated spikes). Two forms exist: a simple scalar stream and a richer vector window.
- Temporal Encoder (Variance / Attention): Lightweight logic that turns recent history into an anomaly score; variance flags volatility spikes, attention highlights structural deviation vs typical pattern.

---
This guide will be ingested into the internal knowledge base / RAG index for analyst self-service.

---

## 12. Vulnerability & SBOM Intelligence (Preview)

Neuron now ingests external vulnerability feeds (NVD / OSV) plus exploit likelihood signals (EPSS probability, KEV catalog) and lets you submit SBOM component inventories. These parts combine to create prioritized "findings" representing real exposure, not just theoretical CVEs.

Quick mental model:
```
Asset -> Components (from SBOM) -> Vulnerabilities (CVE) -> Finding (risk-scored link)
```
Key analyst cues:
- `kev_listed = true` : Actively exploited in the wild (treat with urgency)
- High `epss` (e.g., >0.5) : Elevated probability of near-term exploitation
- `risk_severity` (HIGH / CRITICAL) : Weighted by exploit signals + base severity + (future) asset criticality

Endpoints:
- `GET /vuln/vulnerabilities` (filter: severity, exploit_only)
- `GET /vuln/findings` (risk-prioritized list)
- `POST /vuln/ingest_sbom` (register components for an asset)

For a plain-language deep dive see: `VULN_OVERVIEW.md` (ingested into RAG index).

Roadmap highlights for analysts:
- Real component-to-CVE matching (beyond synthetic demo)
- SLA tracking & finding state transitions
- Correlation of anomaly spikes with high-risk findings
- Stronger cryptographic audit chain for evidence confidence

Action Starter:
1. Ingest SBOM for a critical service.
2. Query findings; note any KEV or high EPSS items.
3. Initiate patch / mitigation workflow for CRITICAL + KEV first.

---