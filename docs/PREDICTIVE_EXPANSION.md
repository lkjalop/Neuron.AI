# Predictive & Automation Expansion (Batch E & F)

This document outlines the initial scaffolding for automation (SLA & anomaly monitoring) and predictive capability placeholders.

## Runtime Gating Parameters
| Param | Purpose | Default |
|-------|---------|---------|
| `automation.enabled` | Enable SLA breach + factor volatility loops | true (implicit) |
| `automation.loop.interval_s` | Poll interval seconds for automation loop | 300 |
| `predictive.enabled` | Enable predictive estimators loop | true (implicit) |
| `predictive.loop.interval_s` | Poll interval seconds for predictive loop | 600 |
| `predictive.exploit.top_n` | Limit exploit likelihood per-CVE gauge emission to top N | (unset => all) |
| `predictive.ttr.severity_weights` | JSON map severity weighting for TTR regression | (unset) |
| `predictive.loop.max_duration_s` | Max allowed predictive iteration duration before cooldown | 10 |
| `predictive.loop.error_burst_threshold` | Consecutive error count triggering cooldown | 5 |
| `predictive.loop.cooldown_s` | Cooldown duration seconds when breaker trips | 300 |
| `alert.enabled` | Master toggle for alert routing | 1 |
| `alert.cooldown.seconds` | Per (type,severity,channel) cooldown | 300 |
| `alert.max_burst` | Channel token bucket capacity | 5 |
| `alert.burst_refill_seconds` | Time to fully refill burst bucket | 300 |

## Automation Components
### SLA Breach Watcher (`SLABreachWatcher`)
- Scans in‑memory findings (placeholder) for age beyond severity SLA window.
- Emits:
  - `neuron_vuln_sla_breach_total{severity}` (counter increment per breach detection)
  - `neuron_vuln_sla_breach_active{severity}` (gauge of currently breached, unfixed)
  - `neuron_vuln_sla_countdown_days{severity}` (existing gauge; min remaining days until SLA) – updated opportunistically.
  - `neuron_vuln_automation_events_total{type="sla_breach"}`

### Factor Volatility Monitor (`FactorVolatilityMonitor`)
- Reads `artifacts/risk_factor_contributions.json` average shares.
- Tracks EW variance per factor → square root as volatility.
- Emits:
  - `neuron_vuln_factor_volatility{factor}` (gauge)
  - `neuron_vuln_anomaly_detections_total{detector="factor_volatility",factor}` on threshold exceed.
  - `neuron_vuln_automation_events_total{type="anomaly"}`

### Alert Dispatcher Placeholder (`AlertDispatcher`)
- Stub for future integrations (e.g., Slack, Jira). Emits `neuron_vuln_alert_dispatch_total{outcome}`.

## Predictive Components
### Time to Remediate Estimator (`TimeToRemediateEstimator`)
- Performs simple linear regression on open findings burn‑down series (from `remediation_timeseries.json` or fallback synthetic points). If `predictive.ttr.severity_weights` provided and burn entries contain `severity_counts`, a weighted open value is used (raw vs weighted persisted in artifact).
- Emits:
  - `neuron_vuln_ttr_estimate_days` (gauge)
  - `neuron_vuln_ttr_confidence` (heuristic confidence)
  - `neuron_vuln_predictive_model_update_total{model="ttr"}`
  - `neuron_vuln_automation_events_total{type="predictive_update"}`
- Artifact: `artifacts/predictive_time_to_remediate.json`

### Exploit Likelihood Model (`ExploitLikelihoodModel`)
- EW moving average of heuristic exploit likelihood combining EPSS + exploit/KEV boosts.
- Emits per-CVE gauge `neuron_vuln_exploit_likelihood{cve}` (top-N emission via `predictive.exploit.top_n`) and aggregated slope `neuron_vuln_exploit_trend_slope`.
- Artifacts: `artifacts/exploit_likelihood_timeline.json`

### Exposure Clustering (`ExposureClustering`)
- Placeholder grouping of open findings by severity label.
- Emits:
  - `neuron_vuln_exposure_cluster_count` (gauge)
  - `neuron_vuln_exposure_cluster_risk{cluster_id}` (gauge)
  - `neuron_vuln_predictive_model_update_total{model="exposure"}`
- Artifact: `artifacts/exposure_clusters.json`

## Unified Automation Events Counter
- `neuron_vuln_automation_events_total{type}` aggregates all automation & predictive loop event types for rate / trend panels (types: sla_breach, anomaly, alert_dispatch, predictive_update).

## Dashboard Additions
Added panels for:
- Active SLA breaches (Critical/High) & 24h breach count.
- Factor volatility timeseries.
- TTR estimate & confidence.
- Top 10 exploit likelihood curves & trend slope.
- Exposure cluster count & cluster risk distribution.
- Automation events hourly increase.

## Circuit Breaker & Reliability
Predictive loop guarded by a lightweight circuit breaker:
1. Track iteration duration; if > `predictive.loop.max_duration_s` enter cooldown.
2. Count consecutive estimator errors; if >= `predictive.loop.error_burst_threshold` enter cooldown.
3. During cooldown `neuron_predictive_loop_state` = 1, otherwise 0.
4. Cooldown events counted in `neuron_predictive_loop_cooldowns_total{reason="time_exceeded|error_burst"}`.

## Multivariate Factor Drift (Placeholder)
- Diagonal Mahalanobis distance approximation over factor share vector.
- `neuron_vuln_factor_mahalanobis_distance` gauge.
- Anomalies: `neuron_vuln_factor_drift_anomalies_total{detector="mahalanobis"}`.

## Alert Routing Scaffold
File: `automation/alerts.py`
- Channel registry (stub `slack_stub`).
- Per (type,severity,channel) cooldown + burst token bucket.
- Metrics: `neuron_vuln_alert_dispatch_total{outcome}`, `neuron_vuln_alert_actionable_total{channel}`, `neuron_vuln_alert_suppressed_total{channel,reason}`.

## Predictive Artifact Integrity Manifest
Each predictive loop iteration hashes model output artifacts and appends JSON lines to `audit/PREDICTIVE_MANIFEST.jsonl` with fields: `ts, path, sha256, size, model`.

## Future Enhancements
| Area | Proposed Improvement |
|------|----------------------|
| SLA | Asset criticality weighting & backlog aging distribution histogram |
| Volatility | Multivariate drift detection (e.g., Hotelling T^2) across factor vector |
| TTR | Segmented regression (piecewise) & confidence bands from residual error |
| Exploit Likelihood | Incorporate external threat intel feed deltas & logistic calibration |
| Clustering | Graph-based clustering using component dependency edges & exposure propagation |
| Alerting | Policy-driven suppression, routing profiles, on-call schedule integrations |
| Forecasting | ARIMA / Prophet style time-series modeling for open findings & exploit curves |
| Feedback Loop | Retrain heuristics using remediation outcome labels (closed vs deferred) |

## Operational Notes
- All loops are best-effort and swallow exceptions to avoid impacting primary scan pipeline.
- Cardinality guarded: exploit likelihood gauge labeled by CVE (bounded by active set size; consider top-N gating later).
- Set `automation.enabled=0` or `predictive.enabled=0` via runtime params to disable respective loops at runtime.

## Roadmap Alignment
This scaffold supports upcoming phases: anomaly-driven alerting, precision/exposure balancing, proactive risk forecasting.

## Recent Enhancements Summary
- Top-N exploit likelihood gating
- Severity-weighted TTR (raw vs weighted persisted)
- Circuit breaker + cooldown metrics
- Multivariate drift detection placeholder
- Alert routing & suppression metrics
- Predictive artifact hashing manifest

## Next RAG Roadmap (Condensed)
Phase A: retrieval evaluation harness (RAGAS), re-ranker, grounding metadata.
Phase B: corrective loop (critic + refinement iterations metrics).
Phase C+: compositional query decomposition & multi-agent orchestration.

Initial version extended – will refine after collecting baseline distributions.
