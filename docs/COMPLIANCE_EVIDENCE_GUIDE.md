# Compliance Evidence Extension

This document provides a concise narrative (Task 11) explaining how Neuron's vulnerability & exposure intelligence capabilities produce evidence to support control objectives across ISO 27001 (Annex themes), NIST CSF Functions, and SOC 2 Trust Services Criteria. It complements `CONTROL_MAPPING.md` by focusing on operational artifacts and how to present them during assessments.

## Core Evidence Artifacts
| Artifact | Generation Path | Integrity Mechanism | Primary Control Themes |
|----------|-----------------|---------------------|------------------------|
| Vulnerability Snapshot JSONL | `/vuln/snapshot` endpoint (script: `scripts/generate_vuln_snapshot.py`) | Chained entry hash + HMAC/ed25519 signature | Vulnerability Management, Monitoring, Evidence Preservation |
| Audit Log (parameter changes / chain) | Runtime param audit (signed chain) | Chained hash + optional ed25519 signatures | Change Management, Governance |
| Feed State Records | `feed_state` table entries | DB row history (timestamp fields) | Monitoring (freshness), Continuous Improvement |
| Findings & Events | `findings` & `finding_events` tables | Immutable event append (state transitions) | Incident Response, Risk Mitigation, Workflow Control |
| SBOM Components & Asset Links | `sbom_components`, `asset_components` tables | Deterministic IDs & referential integrity | Asset Inventory, Vulnerability Identification |
| Risk Scores (with factors) | Recomputed via expanded risk model (`scanner/risk.py`) | Deterministic recomputation using stored params | Risk Assessment & Prioritization |

## Presenting Evidence to Auditors
1. Snapshot Chain Validation:
   - Run the snapshot script twice (different times) and show appended signature records in `audit/VULN_SNAPSHOTS_SIGNATURES.jsonl`.
   - Provide the public key (if ed25519 used) and a verification script (future enhancement) to demonstrate tamper evidence.
2. Parameter Change Governance:
   - Export parameter change log (runtime parameters + audit chain) to show controlled adjustments to risk weights, scan intervals, and enrichment refresh cadence.
3. Timeliness & Freshness:
   - Query `feed_state` to show recent `last_fetch_ts` values for NVD/EPSS/KEV demonstrating operational polling.
4. Prioritization Transparency:
   - Provide sampled finding records including `risk_score`, `risk_severity`, and associated vulnerability fields (exploitability, EPSS, KEV) plus the param weights in effect.
5. State Change Lifecycle:
   - Extract `finding_events` for a representative finding to illustrate the workflow (e.g., open → triaged → fixed) with timestamps.
6. Asset Coverage:
   - Demonstrate SBOM ingestion (`/vuln/ingest_sbom`) followed by `matched_findings` showing environment-specific applicability.
7. Correlation Context (Emerging):
   - Use `/vuln/correlation` (once anomaly asset tagging matures) to show integrated situational awareness for response prioritization.

## Control Theme Alignment Highlights
- Identification: SBOM + matching ensures environment-specific vulnerability detection (reduces noise vs. global list).
- Prioritization: EPSS/KEV + exploit flags + asset criticality weighting yields evidence-based triage.
- Integrity: Chained signatures (audit + snapshots) provide tamper-evident historical record.
- Responsiveness: Refresh loops (enrichment update task) demonstrate ongoing surveillance of exploit intelligence.
- Accountability: State transition events create traceable remediation audit trails.

## Operational Runbook Excerpt
| Goal | Command / Endpoint | Expected Output |
|------|--------------------|-----------------|
| Generate snapshot | `POST /vuln/snapshot` | JSON metadata with hash + signature fields |
| List recent findings | `GET /vuln/findings` | Structured list with risk & state |
| Change finding state | `POST /vuln/findings/{id}/state` | Confirmation + event row inserted |
| Inspect feed freshness | SQL: `SELECT * FROM feed_state` | Rows with `last_fetch_ts` updated recently |
| Recompute risk (implicit) | Occurs during scanner/enrichment loops | Updated `risk_score` values |

## Evidence Packaging Tips
- Export raw JSON (no screenshots) plus cryptographic signature files.
- Provide SHA256 manifest of exported evidence bundle.
- Include runtime parameter snapshot (weights + thresholds) for reproducibility of risk scores.

## Future Enhancement Roadmap (Compliance Lens)
- Add explicit verification CLI for all chain signatures.
- Introduce retention & rotation policy metadata (e.g., snapshot cadence param & retention enforcement logs).
- Expand version range parsing to reduce false positives (accuracy evidence).
- Implement SLA breach detection (finding open time > threshold) with alert events.

## Disclaimer
This narrative is informational; it does not replace official framework guidance. Always corroborate with authoritative documents and professional judgment.
