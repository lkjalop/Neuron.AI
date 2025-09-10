# Resource & Latency Budget (Phase 3 / Pre-Fusion)

Purpose: Define deterministic service-level operating bands for the experimental SNN detector so automatic safeguards (resource guard & redundancy states) are measurable and auditable.

Scope: Applies while `detection.enable_snn` is true. Baseline detector remains authoritative fallback. Provides inputs to redundancy state machine design and future policy-as-code assertions.

## 1. Core Metrics
| Metric | Symbol | Source | Collection | Notes |
|--------|--------|--------|------------|-------|
| Inference Latency p50/p95 | L50, L95 | `SNN_INFERENCE_LATENCY` | Histogram export | Derived ms thresholds.
| Spike Density | D | `SNN_SPIKE_DENSITY` | Gauge set per event | Aggregated sliding window.
| Activity | A | `SNN_ACTIVITY` | Gauge | Used for adaptive thresholds later.
| Guard Triggers | G | `SNN_RESOURCE_GUARDS_TRIGGERED` | Counter | Labeled by reason.
| CPU Process % | CPU | SYSTEM_CPU_PERCENT | Sampler thread | Relative delta vs baseline-only period.
| Memory RSS MB | MEM | SYSTEM_MEMORY_MB | Sampler thread | Delta vs baseline.

## 2. Operating Bands
| Dimension | Green (Normal) | Amber (Observe) | Red (Action) |
|-----------|----------------|-----------------|--------------|
| L95 Added Latency | <5 ms | 5–8 ms | >8 ms |
| CPU Overhead | <10% | 10–15% | >15% |
| Memory Overhead | <25 MB | 25–40 MB | >40 MB |
| Spike Density Mean | 0.05–0.35 | 0.01–0.05 or 0.35–0.5 | <0.01 or >0.5 |
| Spike Density Std Dev | <0.15 | 0.15–0.25 | >0.25 (instability) |
| Guard Trigger Rate | ≤0.5% events | 0.5–1% | >1% |
| Saturation Streak (D >0.5) | <10/50 events | 10–20/50 | >20/50 |
| Starvation Streak (D <0.01) | <10/50 events | 10–20/50 | >20/50 |

## 3. Redundancy / State Machine (Draft)
States:
- `NORMAL`: All bands green or occasional amber (<2 consecutive windows).
- `DEGRADED_SNN_DISABLED`: SNN auto-disabled; baseline only; triggered by Red in latency OR CPU OR memory OR (two concurrent Red density conditions).
- `SAFE_MODE`: Manual or policy-forced broad disable (e.g., suspected model tamper) – future.

Transitions (pseudo):
```
if state == NORMAL and (latency_red or cpu_red or memory_red or density_red_major):
    disable_snn(); state = DEGRADED_SNN_DISABLED; audit(reason)
if state == DEGRADED_SNN_DISABLED and cool_down_elapsed and recent_metrics_all_green_for_N_windows:
    enable_snn(); audit(reenable_reason="auto_recovery")
```

Cooldown: Default 120s (runtime param planned: `snn.guard_cooldown_sec`).
Recovery Condition: Last 3 latency windows Green AND no saturation/starvation Red flags.

## 4. Guard Algorithm Outline
1. Maintain sliding windows (size=50 events) for density and latency classification.
2. Compute summary stats each window close.
3. Evaluate rules; increment `SNN_RESOURCE_GUARDS_TRIGGERED` on each protective action.
4. Persist a simple json state file (optional) for post-mortem (future hardening).

## 5. Audit Requirements
On disable:
- Capture: timestamp, last L95, CPU delta, density stats, reason code.
- Append structured line to `AUDIT_LOG.md` (future: dedicated guard log).
On re-enable:
- Capture: recovery metrics snapshot + elapsed disable time.

## 6. Policy-as-Code Hooks (Forward)
- Rego / DSL rule examples:
  - Deny re-enable if `precision_loss_last_eval > 0.08`.
  - Force SAFE_MODE if 3 disable cycles in 10 min.

## 7. Control Mapping
| Control | Mapping | Justification |
|---------|---------|---------------|
| NIST SI-4 | Continuous monitoring | Latency & density anomaly detection for detector health. |
| NIST SI-7 | Software fault containment | Automatic disable on resource anomaly. |
| ISO 27001 A.8.16 | Monitoring activities | Telemetry-driven state transitions. |
| SOC2 CC7.2 | Change management & operational resilience | Guard transitions audited. |
| ISO/IEC 42001 (AI) – Operability | Maintain performance & risk controls | Resource-aware adaptive disablement. |

## 8. Future Extensions
- Per-tenant SNN enable toggles based on cost/benefit.
- Adaptive density target using rolling quantiles.
- GPU offload metrics (if future architectures introduced).
- Multi-detector arbitration (Phase 4 fusion influence).

## 9. RAG / Knowledge Graph Tags
Tags: `resource_budget`, `phase3`, `redundancy`, `safeguards`
Planned edges:
- DETECTOR(snn) -[HAS_BUDGET]-> RESOURCE_BUDGET(doc)
- RESOURCE_BUDGET -[GOVERNS]-> STATE_MACHINE(node)

## 10. Integrity & Versioning
Document hash captured in next gate report; modifications require audit entry referencing old hash with rationale (e.g., new hardware profile, workload shift).

Status: Draft v1 (activates once guard enforcement implemented).