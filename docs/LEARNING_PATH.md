# Neuron Platform Learning Path (Cram Guide)

Goal: Understand & articulate architecture, safety controls, and rationale for each subsystem.

Cross-Reference: See `PHASE1_2_SUMMARY.md` for a consolidated narrative of achievements, deviations, trade-offs, and Phase 3 readiness rationale. This learning path is the terse cram companion; the summary doc is the narrative evidence bundle.

Phase 2.1 Reliability Focus (Pre-Phase 3 Gate):
- Inline detection path on `/ingest` (optional header/flag) to guarantee anomaly evaluation without queue latency.
- Warm-up jitter in load harness (replace constant warm-up values with slight noise) to avoid permanent zero-variance windows.
- Deterministic drain on shutdown or explicit flush API to ensure injected anomalies are processed & persisted.
- Export verification loop: harness -> wait/flush -> dataset export must yield `anomaly_count > 0` under injection scenario.
- Hash & audit amendment (A11) capturing this reliability scope before enabling any SNN prototype flag.

Tracking Status: Implement after A10 (security & persistence). Gate A11 must be satisfied (anomaly evidence present) before Phase 3 activation.

## 1. Event Schema & Traceability
File: `src/core/event.py`
Key: `event_id`, `tenant_id`, `trace_id`, `features`, `labels`, `version`.
Trace ID supports correlation across processing stages.

## 2. Ingestion & Rate Limiting
Files: `src/core/ingest/manager.py`, `src/core/ratelimit.py`.
Token bucket: prevents resource exhaustion; drop & error metrics recorded.

## 3. Baseline Detection
File: `src/core/detect/baseline.py`.
Rolling mean/std; anomaly if |z| >= threshold after warm-up.

### 3.1 Adaptive Thresholding & MAD
If variance collapses (std=0), we fall back to Median Absolute Deviation (MAD) scaled (~1.4826) to avoid blind spots.
Reasons an anomaly is flagged: `std` (z-score), `mad` (robust), (future) other detectors.

## 4. Metrics & Observability
File: `src/core/metrics.py`.
Counters: events, anomalies, drops, ingest errors, authz decisions; histogram: processing latency.
Added: warm-up skips, MAD fallback counts, system memory / CPU gauges.

## 5. Integrity & Audit
Files: `docs/NEURON_PHASES.md`, `audit/CANONICAL_DOC_HASH`, startup guard in `core/main.py`.
Prevents silent requirements drift.

## 6. IAM Foundations
File: `src/iam/authz.py` (RBAC + ABAC & agent drift hooks).

## 7. Synthetic Evaluation
Files: `scripts/generate_synthetic_events.py`, `scripts/evaluate_baseline.py`.
Purpose: quantify baseline before advanced ML.
Outputs precision, recall, F1; artifact stored at `artifacts/eval/baseline_metrics.json`.

## 8. Phase Gates
Evidence bundles: anomaly quality, latency, resource envelope precede enabling new flags.

## 9. Future (SNN & Fusion)
Planned doc: `docs/SNN_ENCODING.md` (encoding strategy, spike representation, resource targets).

### 9.1 Planned Neuromorphic Layer (Preview)
SNN prototype (Phase 3) will ingest normalized feature vectors -> encoding (rate / latency) -> spiking layer -> aggregated anomaly probability.
We will A/B compare against baseline metrics to justify complexity.

### 9.2 Active Neuromorphic Sprint (Evidence Focus)
Goal: Demonstrate temporal & pattern sensitivity uplift vs baseline before hardening.

Components Added:
- `snn.mode` runtime param: `proto` (original accumulator) or `lif` (snntorch LIF layer) fallback-safe.
- Prediction gauge (`SNN_PREDICTED_ACTIVITY`): exponential smoothing forecast of next activity to explore anticipatory anomaly scoring.
- Energy proxy counter (`SNN_ENERGY_SPIKES_TOTAL`): cumulative spike count as rough efficiency signal.
- Benchmark harness (`scripts/benchmark_neuromorphic.py`): Generates temporal pattern sequences (drift, burst, periodic) and compares anomaly counts + energy.

Analyst Plain Language:
"We gave the system a 'temporal ear'. Instead of only measuring how far a value is from average, we convert values into spike pulses over short windows. A spiking neuron integrates these pulses and produces a pattern-aware activity level. We compare: does this spiking method catch gradual drifts or periodic disruptions sooner or more reliably than the classic math?"

Sprint Acceptance (Minimal Success Criteria):
1. On at least one temporal pattern (drift or periodic), SNN anomaly count > baseline anomaly count without >50% false-looking noise on pure noise windows (manual spot check).
2. LIF mode runs without error (falls back gracefully if torch unavailable).
3. Energy proxy recorded (non-zero) and not exploding superlinearly with events (< 2x spikes/ event over run).

Deferred (Intentionally Not Yet Implemented):
- Label ingestion & calibrated scoring.
- Multi-feature PSI for drift across many dimensions.
- Cognitive agent reasoning (placeholder planned after proving temporal uplift).
- Hash chains / advanced governance (ensure value first).

Next Step After Acceptance: Introduce lightweight cognitive agent that attaches a reason context ("periodic disruption" vs "monotonic drift") using simple pattern heuristics feeding fusion reasoning.

## 10. Response Orchestration (Planned)
Safety: dry-run, approval workflow, cooldown, rollback journal.

### Glossary (Seed)
| Term | Meaning |
|------|---------|
| Trace ID | Correlates processing across stages |
| Token Bucket | Rate limiting via capped refillable tokens |
| Warm-Up | Initial window skipped for anomaly scoring |
| Baseline Detector | Statistical model (mean/std) to flag outliers |
| MAD | Median Absolute Deviation – robust dispersion measure |
| Precision | Share of flagged events that were truly anomalous |
| Recall | Share of true anomalies the system caught |
| F1 | Harmonic mean of precision & recall |
| Runtime Parameter | Tunable setting changed without redeploy |
| Secret | Sensitive value like API key, requires restricted handling |

### Self-Assessment Checklist
| Topic | Explain? | File Pointer | Risk if Broken |
|-------|----------|--------------|----------------|
| Event schema |  | event.py | Data inconsistency |
| Rate limiting |  | ratelimit.py | Resource exhaustion |
| Baseline detector |  | baseline.py | High FP/FN |
| Runtime params |  | config/runtime_params.py | Uncontrolled tuning |
| Secrets handling |  | security/secrets.py | Key leakage |
| Evaluation quality |  | evaluate_baseline.py | Misleading metrics |
| Anomaly buffer |  | shared_anomalies.py | Lost visibility |

## 11. Runtime Parameters & Governance
Central registry holds thresholds (stddev, warm-up) & flood gate factors. Changes are:
1. Validated against schema ranges.
2. Logged to `audit/param_changes.log`.
3. Future: RBAC/ABAC + multi-party approval.

## 12. Secrets & Key Management (Stub)
Environment variable loader with TTL cache; future: Vault/KMS integration, rotation events, access audit.

## 13. Failure & Recovery Playbook (Scaffold)
| Symptom | Likely Cause | Immediate Action | Long-Term Fix |
|---------|--------------|------------------|---------------|
| High FP spike | Threshold too low | Raise stddev param | Adaptive threshold tuning / new features |
| No anomalies at all | Threshold too high or warm-up never ends | Lower stddev / inspect warm-up | Feature scaling validation |
| Endless warm-up skips | Detector state resetting | Confirm single detector instance | Persist state across restarts |
| MAD fallback always | Feature constant | Validate data generation | Add richer feature set |
| Memory growth | Buffer too large | Trim per-tenant limit | Persist + rotate storage |

## 14. Investor / Analyst Quick Pitch
"Neuron builds trustworthy anomaly intelligence progressively: auditable specs, governed tuning, baseline evidence, then neuromorphic expansion."

## 15. RAG / Knowledge Graph Future
All docs (this path + glossary + gate reports) will feed a retrieval index enabling natural language Q&A for analysts (Phase ≥4 readiness). Preparing consistent structure now reduces later curation cost.

| Metrics integrity |  | metrics.py | Blind spots |
| Canonical doc hash |  | main.py | Silent drift |

> Populate explanations & risks as you study; use this as cram reference before client / audit review.

---

## 16. Deep Dive Modules

### 16.1 Statistical Foundations (Non-Technical)
Analogy: We watch a *heartbeat* (feature values). When beats stray too far from their usual rhythm (mean) more than a tolerated number of times (threshold in standard deviations), we raise a hand. If the rhythm is too steady (zero variance), we compare each beat to the middle beat (median) and how far typical beats stray (MAD).

Key Intuitions:
- Standard deviation: "average surprise" distance.
- Z-score: how many surprise units away.
- MAD fallback: resistant to a few extreme outliers.

### 16.2 Robustness Trade-Off
| Approach | Strength | Weakness | When Preferred |
|----------|----------|----------|----------------|
| Mean/Std | Fast, common | Sensitive to outliers | Stable distributions |
| MAD | Outlier resistant | Less efficient small n | Low variance / spikes present |
| Future SNN | Temporal/spatial pattern capture | Higher resource cost | Complex temporal anomalies |

### 16.3 Multi-Tenancy Isolation Risks
| Risk | Description | Mitigation | Residual |
|------|-------------|-----------|----------|
| Cross-tenant data leak | Features merged | Per-event validation + tenant set | Medium (needs IAM hardening) |
| Noisy tenant skews thresholds | Shared detector state | Per-tenant state dict | Low |
| Parameter drift across tenants | Inconsistent tuning | Param registry with scoping (future) | Medium |

### 16.4 Parameter Governance Flow (Narrative)
You observe an anomaly flood in tenant A. You run the threshold sweep script, find that F1 improves with threshold 3.2→3.5 reducing FP by 28% while recall drops only 2%. You submit a rationale (JIRA-123), apply via admin param endpoint, system logs audit entry A0X with before/after snapshot.

### 16.5 Failure Pattern Catalog (Extended)
| Pattern | Signal | Triage Question | Automated Assist |
|---------|--------|-----------------|------------------|
| Feature Freeze | Storm of warm-up skips persists | Is state resetting? | Health state machine marks DEGRADED |
| Alert Storm | Anomaly rate > flood threshold | Legit spike or noise? | Auto threshold sweep suggestion |
| Silent Detector | Anomaly rate near zero unexpectedly | Data feed alive? | Liveness check in ingestion |
| Resource Creep | Gradual MB climb | Leak vs buffer growth? | Periodic snapshot diff |

### 16.6 SNN Preview (Conceptual)
SNN approximates biological neurons: events encoded into spike trains; neurons integrate spikes and fire if membrane potential crosses threshold, creating time-dynamic patterns. Benefit: temporal sensitivity; Risk: complexity + energy cost.

### 16.7 Failsafe Storyboard
1. Latency spikes -> DEGRADED -> disable shadow modules.
2. Second regression -> SAFE_MODE -> baseline only.
3. Operator acknowledges after stable window -> RECOVERY.
4. Gradual re-enable detectors -> NORMAL.

## 17. Quiz ( formative )
Answer succinctly; rationale more important than jargon.

| # | Question | Your Answer |
|---|----------|-------------|
| 1 | Why do we need a warm-up period? | |
| 2 | What problem does MAD solve vs std? | |
| 3 | One sign baseline threshold is too low? | |
| 4 | Why separate detector state per tenant? | |
| 5 | What triggers SAFE_MODE? | |
| 6 | How do you justify raising threshold from 3.0 to 3.4? | |
| 7 | Primary risk of enabling SNN too early? | |
| 8 | Purpose of the canonical doc hash? | |
| 9 | Metric to watch for silent detection failure? | |
|10 | Single sentence: what is uplift? | |

## 18. Non-Technical Summary Card
"Neuron watches streams of system heartbeat patterns. It learns typical rhythms for each tenant. When a beat is weird enough, it raises a governed, explainable flag—only adding fancier (neuromorphic) senses once the basic ones have proven their value."

## 19. Suggested Practice Drills
- Run synthetic generator, tweak threshold, record precision/recall deltas.
- Simulate anomaly flood and interpret metrics.
- Manually corrupt canonical doc and observe startup guard behavior.

## 20. Next Expansion Hooks (Placeholders)
- SNN encoding walkthrough (pending Phase 3).
- Fusion calibration tutorial (Phase 4).
- Response playbook dry-run scenario (Phase 5).

## 21. Test Methodology & Baseline Validation (Non-Technical View)
Why we test: To prove the current "simple baseline" is stable, trustworthy, and measurable before introducing more complex (and harder to debug) neuromorphic components.

Test Categories:
| Category | File(s) | Purpose | Risk if Fails | Plain Language Analogy |
|----------|---------|---------|---------------|------------------------|
| Event Contract | `test_event.py` | Ensure core message shape accepted | Data chaos | The envelope format is correct |
| Rate Limiting | `test_rate_limiter.py` | Prevent overload fairness | Service stall | Turnstile counts entrants |
| Detector Logic | `test_baseline_detector.py` | Flags true outliers | Missed attacks or noise flood | Metal detector sensitivity |
| Metrics Integrity | `test_metrics_integrity.py` | Counters monotonic & latency recorded | Blind monitoring | Gauges not stuck |
| Failure Injection | `test_failure_injection.py` | Error paths increment proper metrics | Silent degradation | Alarm lights wired |
| Tenant Isolation | `test_tenant_isolation.py` | Per-tenant statistical separation | Cross-tenant leakage | Separate water pipes |
| Manifest Guard | `test_manifest_guard.py` | Canonical doc immutability enforced | Spec drift | Blueprint tampering alarm |
| IAM Scaffold | `test_iam.py` | Basic authorization gate (viewer read) | Uncontrolled access | Front desk badge scan |

How we run them (operator steps):
1. Install deps: `pip install -r requirements.txt`
2. Run suite: `python -m pytest -q`
3. On failure: read assertion message -> open referenced file -> apply minimal fix -> re-run failing test (`-k <name>`)
4. Regenerate artifacts (evaluation + gate report) if change influences detection thresholds.

Baseline Quality Loop:
1. Generate synthetic dataset (script).  
2. Evaluate baseline -> capture precision/recall/F1.  
3. Sweep thresholds -> auto-apply best (audited).  
4. Re-run tests (ensures no regression).  
5. Generate gate report (hash all artifacts).  

Why include in RAG / Wiki:
- Retrieval: Future incident responders can ask "Why did threshold change?" and vector search returns sweep rationale & audit trail.
- Onboarding: New analysts self-serve test purpose without code dive.
- Drift Detection: RAG comparisons highlight when a previously green test category now failing (knowledge diff).
- Compliance: External auditors can query "Show evidence of spec immutability guard" and retrieve manifest guard test & latest pass.

Future Automation Hooks:
- Auto-threshold sweep suggestion triggered when FP rate > X for Y minutes.
- ChatOps summary posting daily test health scoreboard.
- Embedding of quiz questions + answers once validated for knowledge graph.

Key Principle: We don't add complexity (SNN) until the simplest measurable layer is demonstrably correct and governed—tests are the living proof artifacts of that discipline.

## 22. Governance Hardening (A09 Additions)
New Controls Introduced:
| Control | File(s) | Purpose | Risk Mitigated |
|---------|---------|---------|----------------|
| API Key Guard | `core/main.py` (require_api_key) | Restrict admin param changes | Unauthorized tuning / drift |
| Hybrid Detection Flag | `config/runtime_params.py`, `baseline.py` | Combine Z-score & MAD paths | Evasion via variance collapse |
| Integrity Verification Script | `scripts/verify_integrity.py` | Recompute & validate artifact hashes | Silent artifact tamper |
| Threat Model | `docs/THREAT_MODEL.md` | Enumerate attack vectors | Untracked risk surface |
| Anomaly Injection Harness | `scripts/load_harness.py` (flags) | Force non-zero anomalies for export | Empty dataset masking failures |

Usage Quickstart:
1. Set admin key: `setx ADMIN_API_KEY <value>` (restart shell)  
2. List params: curl with header `x-api-key: <value>` → `/admin/params`  
3. Enable hybrid: POST update `{"key":"baseline.use_hybrid","value":true,"reason":"enable_hybrid"}`  
4. Run load with anomalies: `python scripts/load_harness.py --inprocess --inject-anomalies --events 120`  
5. Export dataset: `python scripts/export_dataset.py` (expect anomaly_count > 0)  
6. Verify integrity: `python scripts/verify_integrity.py --gate artifacts/gate_report/gate_report_<ts>.json`  

Why Before SNN:
Hardening governance now reduces compounded uncertainty when more complex temporal detectors arrive—keeping blast radius small and evidence reproducible.

RAG Benefit:
Queries like "How do we verify artifacts?" or "What mitigates parameter tampering?" retrieve the new sections & script references.

---

## 23. SNN Threshold & Calibration (Non-Technical SOC Summary)

Purpose: Ensure analysts understand what the neuromorphic (SNN) threshold does, how it differs from "training", and when to adjust it.

### 23.1 Is This Training?
Not yet. We are NOT learning weights via gradient descent. We are tuning a decision boundary (threshold) and choosing an encoding (rules for turning numbers into spikes). This is adaptive configuration, not model training. True training would involve labeled examples and optimization of neuron weights.

### 23.2 Why a Threshold?
Spiking activity is a running energy/pattern signal. The threshold answers: "Is this activity sufficiently unusual vs our tolerance?" Lower threshold = more anomalies (risk of noise). Higher threshold = fewer anomalies (risk of misses).

### 23.3 Healthy Targets
| Metric | Early Target | Reason |
|--------|--------------|--------|
| SNN/Base Anomaly Ratio | ~2.0× (1.5–3.0 acceptable) | Show added temporal sensitivity without flooding |
| SNN Unique Ratio (SNN-only / union) | 10–30% | Some novel catches; avoid overwhelming divergence |
| SNN Anomaly % of Events | < 8% | Analyst workload safety band |
| Energy (spikes/event) Trend | Stable / sublinear | Efficiency guard |

### 23.4 Manual Adjustment Loop (If Auto-Cal Off)
1. Run benchmark or sample 5–10k events.
2. Compute baseline anomalies (B) and SNN anomalies (S).
3. Ratio R = (S+1)/(B+1).
4. If R > 3 → raise threshold ~15–25%. If R < 1 → lower threshold ~10–15%. Else hold.
5. Re-run sample; log rationale (audit).

### 23.5 Future Auto-Calibration (Planned Replacement)
Interval-based controller: every N events compare ratio to target band and shift threshold stepwise (bounded). No micro jitter; explicit recalibration points.

### 23.6 Encoder Evolution
| Encoder | Mechanism | Benefit | Risk |
|---------|----------|---------|------|
| rate_v1 | Simple rate from normalized magnitude | Deterministic, fast | Over-fires on broad scale shifts |
| rate_v2 (planned) | Robust median/MAD scaling + burst gating | Captures sudden surges fairly | Complexity; needs tests |

### 23.7 When to Investigate
| Symptom | Likely Cause | Action |
|---------|--------------|--------|
| SNN flood, baseline quiet | Threshold too low | Increase threshold / inspect encoder density |
| SNN silent, baseline active | Threshold too high | Lower threshold; verify spikes present |
| Energy climbing steeply | Encoder producing dense spikes | Apply density cap or scale factor cut |
| Unique ratio >60% sustained | Possible noise inflation | Tighten threshold; review sample anomalies |

### 23.8 Plain Language Elevator Pitch
"We gave the detector a temporal sense. The threshold is its patience dial: too low and it shouts constantly; too high and it misses whispers. We tune that dial against a simple baseline to prove benefit before adding real learning."

### 23.9 FAQ (SOC)
| Question | Short Answer |
|----------|--------------|
| Is SNN learning? | No, threshold tuning only (for now). |
| Why higher anomaly count ok? | Temporal sensitivity should add signal, but bounded. |
| What proves value? | Sustained uplift with acceptable noise & stable energy. |
| Can attacker game it? | Yes, via flood or starvation; we monitor density & ratio. |
| When escalate? | If ratio >3.5 or unique ratio spikes >50% for >2 windows. |

---

