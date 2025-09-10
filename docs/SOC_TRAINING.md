# SOC Training & Adversarial Scenarios (Phase 3)

Purpose: Provide operator playbooks, adversarial scenario catalog, and firefighter (automated triage) concept to ensure governed response and resilience for the experimental SNN detector prior to fusion stage.

Status: Draft v1

## 1. Roles & Responsibilities
| Role | Primary Actions | Escalation Path |
|------|-----------------|-----------------|
| SOC Analyst (Level 1) | Monitor anomaly queues, acknowledge alerts, verify guard dashboards | Escalate to L2 on detector health degradation |
| Detection Engineer (L2) | Re-run evaluation sweeps, adjust governed params via runtime API, review guard disable events | Escalate to Security Architecture |
| Firefighter Agent (Automated – future) | Detect repeated disable cycles, classify root cause, trigger fallback policy | Notify L2 + incident channel |
| Security Architecture | Approve threshold or policy changes, sign off on re-enable after major incident | Executive risk committee |

## 2. Key Telemetry & Dashboards
- Detector Performance: Precision, Recall, F1 (from latest eval artifact).
- Resource Health: p95 latency, spike density band, guard trigger rate.
- State Indicators: `detection.enable_snn` flag, cooldown timer, disable streak count.
- Integrity: Hashes of `UPLIFT_TARGETS.md`, `RESOURCE_BUDGET.md`, `SNN_THRESHOLD_RATIONALE.md` captured in gate report.

## 3. Adversarial Scenario Catalog
| ID | Scenario | Vector / Method | Expected Signal | Guard / Control Response | Playbook Reference |
|----|----------|-----------------|-----------------|---------------------------|--------------------|
| ADV-01 | Precision Flood via Low Threshold | Misconfig or malicious param change (<2.5) | Spike in predicted anomalies, precision collapse | Governance fails threshold change if audit reason absent; analysts observe alert surge | PB-01 |
| ADV-02 | Silent Suppression via High Threshold | Raise threshold >3.5 toward max | Recall drop to 0, spike density normal | Schema cap + periodic evaluation gap detection | PB-02 |
| ADV-03 | Latency Exhaustion | Adversary crafts feature payloads to increase encode time | Rising p95 latency; guard triggers disable | Auto cooldown disable; firefighter agent (future) classifies cause | PB-03 |
| ADV-04 | Density Saturation | Features pegged at extreme values -> high spike density | Density >0.5 sustained | Guard triggers; disable if repeated | PB-04 |
| ADV-05 | Starvation Evasion | Minimal feature magnitudes to evade spikes | Density <0.01 + recall slump | Evaluation detects recall loss; potential adaptive rate scaling later | PB-05 |
| ADV-06 | Hash / Integrity Tamper | Attempt to modify governance docs without audit | Hash mismatch in gate report | Incident: freeze threshold changes | PB-06 |
| ADV-07 | Rapid Disable Cycling | Repeated latency spikes causing multiple cooldowns | >3 disables / 10 min | Firefighter escalation | PB-07 |
| ADV-08 | Data Poisoning (Baseline Drift) | Inject anomalous values during warmup | Shifted baseline stats, delayed anomaly detection | Warmup min + MAD fallback reduce impact | PB-08 |

## 4. Playbooks (PB-01..PB-04 Excerpt)
### PB-01 Precision Flood
1. Confirm anomaly volume vs normal baseline window.
2. Verify `snn.threshold` value (should be 3.0) via param listing.
3. If mis-set and audit reason absent: revert using `update_param` with reason `precision_recovery`, log incident.
4. Run partial evaluation (50-event sample) to confirm precision restoration.

### PB-02 Silent Suppression
1. Detect by scheduled sweep (fails recall uplift criteria) or zero anomalies over N windows.
2. Compare `snn.threshold` to rationale doc.
3. If >3.0 without approved change: revert & re-run sweep.
4. If threshold unchanged: investigate encoder / density starvation (see PB-05).

### PB-03 Latency Exhaustion
1. Inspect guard triggers labeled `resource_guard`.
2. Extract last p95 latency from metrics.
3. Identify input feature patterns (large vector sizes?).
4. Increase cooldown param temporarily if thrashing; open incident.
5. Consider enabling SAFE_MODE (future) if repeated.

### PB-04 Density Saturation
1. Validate density >0.5 sustained.
2. Acquire sample feature distribution snapshot.
3. If attacker-driven, deploy filter (drop extreme fields) and re-evaluate.
4. If organic drift, plan adaptive scaling update.

### PB-05 Starvation Evasion
1. Confirm density <0.01 over at least 2 latency windows.
2. Re-run evaluation sweep; verify recall uplift now < target.
3. Inspect feature magnitude distribution (are all near zero?).
4. Mitigation: enable temporary adaptive rate scaling (future) or enforce minimum feature normalization floor.
5. If malicious input filtering suspected, add rule to reject all-zero / near-zero feature sets.

### PB-06 Integrity Tamper
1. Gate report generation shows hash mismatch (compare expected vs recomputed).
2. Immediately freeze runtime param changes (lock admin interface except read-only).
3. Capture diff of modified doc(s) and open incident ticket.
4. Restore last known-good hash from version control; regenerate report.
5. Root cause & commit sign-off required before unfreeze.

### PB-07 Rapid Disable Cycling
1. Firefighter incident `snn_disable_cycle` with cycles >= threshold.
2. Extract recent guard trigger reasons and latency/density stats.
3. If dominated by latency: increase cooldown param slightly (e.g., +50%) and profile slow path.
4. If dominated by density: apply temporary feature clamp.
5. After stabilization, revert cooldown param; log adjustments.

### PB-08 Data Poisoning (Baseline Drift)
1. Identify abnormal shift in baseline mean/std vs prior window.
2. Cross-check warmup period—were many extreme values injected early?
3. Run verification script on dataset integrity (line counts, manifest root) to exclude ingestion corruption.
4. Mitigation: reset baseline model state; quarantine suspect events; perform targeted sweep to verify recovery.
5. Consider expanding MAD fallback weighting until new stable baseline achieved.

## 5. Firefighter Agent Concept
Minimal responsibilities (Phase 3 stub):
- Count guard-triggered disable cycles (cooldowns) within sliding 10-minute window.
- Emit structured incident: `{type:"snn_disable_cycle", cycles:N, window_sec, threshold}` persisted to `incidents.log`.
- Auto-suppress duplicate incidents (cooldown window).

Roadmap Enhancements:
- Root cause classifier (latency vs density vs precision flood) using recent metric vectors.
- Ticketing integration (Jira/ServiceNow stub) to auto-create incident tickets with prefilled metrics snapshot.
- Slack / ChatOps notifier integration with rate limiting.
- Auto param suggestions (increase cooldown, adjust threshold) with human confirmation gate.
- Confidence scoring for each recommendation (e.g., based on metric divergence magnitude).

Noise Avoidance Principles:
- Exponential backoff on repeated identical incident types.
- Suppress incidents if SNN already disabled > 50% of last hour (avoid redundant noise).
- Aggregate metrics deltas (min/avg/max) instead of dumping raw arrays.

Data Retention:
- Rotate `incidents.log` daily (future task) keeping last N days (configurable) to prevent unbounded growth.

Security Hardening (see Section 12): ensure no direct execution hooks triggered by incident payload content.

## 6. Incident Lifecycle
| Stage | Action | Owner | SLA |
|-------|--------|-------|-----|
| Detect | Guard trigger / firefighter incident | System / Agent | Real-time |
| Triage | Validate metrics & severity | L1 Analyst | 5 min |
| Contain | Revert param / hold threshold | L2 Engineer | 15 min |
| Eradicate | Patch root cause (e.g., feature filter) | L2 Engineer | 1 business day |
| Recover | Re-enable SNN, re-run evaluation | L2 + Architecture | 2 hours |
| Review | Post-mortem + doc hash update | Architecture | 3 days |

## 7. Metrics to Track in Drills
- MTTR (disable -> re-enable)
- False disable rate
- Incident duplicate suppression effectiveness
- Analyst handling time

## 8. Training Drill Template
1. Seed scenario (e.g., ADV-03) with synthetic event pattern.
2. Observe system metrics; ensure guard triggers.
3. Execute relevant playbook steps; measure times.
4. Log actions & decisions; compute SLA compliance.
5. Debrief & update this doc if gaps discovered.

## 9. Control Mapping
| Control | Justification |
|---------|---------------|
| NIST SI-4 | Continuous monitoring & anomaly response drills |
| NIST SI-7 | Automated fault containment (resource guard) |
| SOC2 CC7.2 | Incident detection & response procedures |
| ISO 27001 A.8.16 | Operational monitoring & incident handling |
| ISO/IEC 42001 | AI operational resilience & risk governance |

## 10. RAG / Knowledge Graph Tags
Tags: `soc_training`, `adversarial`, `playbook`, `firefighter_agent`, `phase3`.
Planned edges:
- PLAYBOOK -> ADVERSARIAL_SCENARIO
- INCIDENT -> PLAYBOOK
- FIREFIGHTER_AGENT -> INCIDENT (generated)

## 11. Update & Integrity

## 12. Firefighter Security Hardening
| Area | Risk | Mitigation |
|------|------|------------|
| Input Poisoning | Crafted events force constant disable cycles to spam incidents | Rate-limit incident generation; density/latency thresholds tuned; add dedupe hash. |
| Log Injection | Malicious content inserted into incidents.log | JSON serialization only; reject entries > size limit; future: signature of log lines. |
| Privilege Escalation | Firefighter suggesting dangerous param changes | Require human approval & audit reason before applying any suggested update. |
| DoS via Large Log | Unbounded incidents growth slows report generation | Implement log rotation & max size checks (future task). |
| Tamper of Governance Docs | Agent used to mask changes | Cross-verify doc hashes in gate report vs runtime; immutable baseline for comparison. |
| Replay / Spoofed Incident | External actor posts fake incident via API | Incidents are append-only local file; API only reads; no external post route exposed. |

Threat Model Notes:

KPIs for Usefulness:

## Phase 4 Addendum: Fusion & Temporal Quick Card

### Plain Purpose
"Fuse stable statistical anomalies with temporal neuromorphic signals; auto-filter low-confidence temporal noise to raise coverage without flooding analysts."

### New KPIs
| KPI | Description | Analyst Action |
|-----|-------------|----------------|
| Uplift Ratio | Added anomalies vs baseline | If <1.1 for 2 cycles -> review SNN threshold/weights |
| Precision Proxy Rate | False positives in noise windows | If >0.05 (50 windows) -> raise suppression threshold |
| Suppression Rate | % SNN-only anomalies filtered | If >0.85 sustained -> consider fallback strategy |
| Residual Mean Contribution | Avg positive forecast residual | Sudden >2x jump -> inspect feature drift |

### Fusion Strategy (Weighted Sum)
```
decision_score = w_b * baseline_indicator + w_s * snn_norm
Suppress if baseline_indicator=0 and decision_score < fusion.weighted_sum.suppress_threshold
```

### Escalation Triggers
| Condition | Immediate Response | Follow-up |
|-----------|--------------------|-----------|
| Precision Proxy Rate breach | Increase suppression threshold +0.05 | Re-check after 200 events |
| High Suppression Rate | Switch to baseline_priority | Investigate SNN noise source |
| Residual Mean Spike | Mark time window | Evaluate for model retrain / calibration |

### MITRE Mapping Snapshot
| Pattern | Hypothesis |
|---------|-----------|
| periodic_shift | Beaconing / Scheduling abuse |
| burst | Exfiltration staging |
| drift | Living-off-the-land persistence |

### Safe Change Rules
1. One param change per 200-event evaluation window.
2. Always include reason (audited).
3. Avoid simultaneous threshold + weight changes unless incident.

### Coming Soon (Phase 5)
Adaptive suppression controller, TFT residual forecasting, rule pack integration, KPI dashboard tiles.
End of Draft v1.

---
## Appendix A: SNN Threshold & Calibration Cheat Sheet (Analyst)

| Concept | What It Means | Action Trigger |
|---------|----------------|----------------|
| Activity | Spiking energy aggregate | Compare vs threshold |
| Threshold | Decision boundary | Adjust if ratio drift persists |
| Uplift Ratio | (SNN+1)/(Baseline+1) | >3 shrink, <1 expand |
| Unique Ratio | SNN-only / union | >60% review noise |
| Energy | Spike total proxy | Rapid growth investigate encoder |

### Calibration Flow (Manual)
1. Sample window → gather B, S
2. Compute R = (S+1)/(B+1)
3. Adjust threshold if R outside [1,3]
4. Log rationale (audit param change)

### Not Training Yet
No weight updates; just structural heuristics + threshold. This keeps governance simple while we gather evidence of temporal benefit.

### Anticipated Upgrade Path
1. Stabilize robust encoder (rate_v2)
2. Add interval auto-calibration service
3. Introduce trainable readout (labeled windows)
4. Add precision feedback loop (optional)

### Red Flags
| Signal | Concern | Escalate? |
|--------|---------|-----------|
| R > 5 two windows | Flood or mis-set threshold | Yes |
| R < 0.5 sustained | SNN not contributing | Yes |
| Unique > 70% | Diverging from baseline | Yes |
| Energy variance spike | Encoder instability | Yes |

### Quick Decision Tree
If flood → raise threshold → re-eval.
If silence → lower threshold → confirm spikes exist.
If balanced but energy high → inspect encoder density → maybe cap.

### One-Sentence Value Statement
"Temporal spikes add early warning; threshold ensures we’re adding insight, not noise."

---
