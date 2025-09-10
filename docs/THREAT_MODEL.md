# Threat Model (Phase 2 Governance Hardening)

Scope: Current statistical baseline service, parameter registry, audit artifacts, synthetic evaluation & load tooling.

## Assets
- Canonical specification (`docs/NEURON_PHASES.md`) & hash
- Runtime parameter values (`config/runtime_params.defaults.json` and in-memory registry)
- Audit logs (`audit/AUDIT_LOG.md`, `audit/param_changes.log`)
- Detection integrity (anomaly decisions & metrics)
- Secrets (API key for admin endpoints)
- Gate report artifacts & hashes

## Trust Boundaries
| Boundary | Description | Notes |
|----------|-------------|-------|
| Admin API | `/admin/params*` endpoints now API key gated | No IAM roles beyond key yet |
| Ingestion | `/ingest` accepts event JSON | Minimal validation; assumes upstream tenant auth |
| Filesystem | Artifact + audit storage | Writable by process; no tamper daemon |
| Parameter Registry | In-memory + persisted defaults | Controlled via audited updates |

## Threat Categories (STRIDE style)
| Category | Vector | Impact | Mitigation | Residual Risk |
|----------|--------|--------|------------|---------------|
| Spoofing | Use stolen API key to alter params | Detection drift | API key secret + audit trail | Key reuse, no rotation policy yet |
| Tampering | Modify gate artifacts to misrepresent baseline | Compliance deception | Hashes + verify script + canonical doc hash | Hash file & report stored same medium |
| Repudiation | Actor denies making param change | Audit param log w/ reason | Missing cryptographic signing |
| Information Disclosure | Reading anomaly buffer or params unauth | No auth on anomalies endpoint | Planned IAM enforcement | Data inference possible |
| Denial of Service | Flood /ingest with high volume | Rate limiter (backpressure metrics) | Detector compute scaling limits |
| Elevation of Privilege | Bypass admin guard by header injection | Single header check | Lack of nonce / HMAC, but suffices Phase 2 |

## Attack Scenarios
1. Silent Spec Drift: Attacker edits `NEURON_PHASES.md`; startup guard blocks unless override env set.
2. Parameter Drift Injection: Attacker uses leaked key to lower threshold ⇒ Higher FP storm → Operator fatigue.
3. Artifact Substitution: Replace `baseline_metrics.json` with inflated F1; verify script flags hash mismatch.
4. Replay /ingest Flood: Exhaust queue → event drops; metrics show spikes in `neuron_events_dropped_total`.
5. Zero-Variance Evasion: Adversary sends constant feature then slight drift just below threshold; hybrid MAD+Z reduces gap.

## Mitigation Roadmap (Pre-SNN Priority)
1. Add HMAC-signed admin requests (key + timestamp) to defeat replay.
2. Per-tenant auth & RBAC on anomalies listing.
3. Separate hash ledger stored append-only (e.g., immutability service or remote KV with versioning).
4. Anomaly buffer size limits + eviction policy to prevent memory pressure.
5. Security scanning integration (already stub script) into CI pipeline.

## Detection Quality Risks
| Risk | Description | Current Control | Planned |
|------|-------------|-----------------|---------|
| Low Recall | Conservative threshold | Threshold sweep + audit | Hybrid / multivariate features |
| Model Drift | Feature distribution shifts | Manual sweeps | Scheduled sweeps + drift alerts |
| Adversarial Injection | Crafted benign-look anomalies | MAD fallback | Multi-feature correlation (Phase 3+) |

## Key Security Metrics (Future)
- Admin auth failures / hour
- Integrity verification job success rate
- Param change frequency + out-of-hours changes
- Anomaly buffer saturation percent

## Summary
Phase 2 focuses on foundational integrity (hashes, audit, governed params). High-impact next steps: stronger admin auth (HMAC), tenant-scoped anomaly access, cryptographic signing of audit artifacts. This staged investment balances velocity with measurable controls before SNN complexity increases attack surface.

## MITRE ATT&CK Mapping (Current & Planned)

| ATT&CK Tactic | Technique (Example) | Observable Pattern / Feature Proxy | Current Coverage (Baseline / SNN) | Planned Enhancement (Temporal / Fusion) | Notes |
|---------------|---------------------|------------------------------------|-----------------------------------|------------------------------------------|-------|
| Reconnaissance | T1046 Network Service Scanning | Periodic low-variance spikes then widened feature spread | Baseline partial (threshold crossings) | Temporal sequence model to distinguish benign cron vs structured scan cadence | Add port/service dimensionality later |
| Resource Development | T1587 Develop Capabilities | Unusual preparatory process resource signature | Not covered | Process lineage + temporal correlation | Requires enriched event schema |
| Initial Access | (Phishing derived) | Sudden CPU/mem burst in new process context | Baseline partial (magnitude) | Fusion weighting with behavioral prior | Needs process ancestry |
| Execution | T1059 Command/Script Interpreter | Rapid feature change sequences (CPU, syscalls) | SNN proto (spike density) | Temporal encoder improves token-level pattern capture | RateEncoderV2 already normalizes outliers |
| Persistence | T1053 Scheduled Task | Repeating interval anomalies with gradual drift | Weak (baseline resets each event) | Transformer seasonal pattern differentiation | Requires multi-window context |
| Privilege Escalation | T1068 Exploitation for Priv Esc | High entropy spike cluster post low activity | SNN partial (burst spike) | Fusion with residual forecast deviation | Need richer feature set |
| Defense Evasion | T1027 Obfuscated/Encrypted Files | Anomalous sustained memory & IO pattern | Not covered | Add feature channels (IO rate) + temporal model | Channel expansion required |
| Credential Access | T1555 Credentials in Files | Access pattern anomaly (future file events) | Not covered | File access sequence model | Outside current scope |
| Discovery | T1087 Account Discovery | Repeated small queries (low amplitude) | Baseline weak (sub-threshold) | Temporal accumulation + SNN low-rate spike gating | Lower suppression threshold tuning |
| Lateral Movement | T1021 Remote Services | New peer connection spike pattern | Not covered | Graph + temporal correlation | Future network telemetry ingest |
| Collection | T1119 Automated Collection | Aggregated sustained resource usage | Partial (elevated baseline metrics) | Forecast residual + fusion suppression heuristics | Add rolling residual gating |
| Exfiltration | T1041 Exfil over C2 Channel | Long-duration moderate spikes (low FPs) | Not covered | Temporal drift + uniqueness ratio trending | Needs network volume features |
| Command & Control | T1071 Web Protocols | Regular beacon intervals | Weak | Transformer positional encoding to identify fixed-interval beacons | SNN spike rhythm may help but limited |

Legend: "Partial" = signal present but high FP/low recall; "Not covered" = requires new features or model class.

### Fusion Strategy Alignment
- Weighted Sum: Will incorporate temporal anomaly score once transformer enabled.
- Suppression Metrics: Used to catch over-aggressive complementary detections (defense evasion risk if suppression too high).
- Unique Ratio Rolling: Early proxy for complementarity; high sustained SNN-unique without overlap triggers deeper review.

### Roadmap Hooks
- Add runtime param: `detection.temporal.enable_transformer` (planned) behind experimental flag.
- Extend event schema for network & process lineage to unlock Discovery / Lateral Movement mapping.
- Introduce drift KPIs per tactic cluster for executive surface (e.g., beacon_suspect_score).
