# Control Mapping (High-Level Reference)

This document provides a high‑level, non‑authoritative mapping between Neuron's vulnerability & exposure intelligence capabilities and representative control domains from major frameworks. It does NOT reproduce framework text; it summarizes how features can support control objectives. Always consult the official standard for definitive requirements.

## Scope
Covered capability areas:
- SBOM ingestion & software asset inventory
- Vulnerability feed ingestion (NVD / OSV placeholder, EPSS, KEV)
- Component→CVE matching & finding lifecycle
- Risk scoring & prioritization (severity, exploitability, asset criticality – planned expansion)
- State transitions & workflow audit (finding_events)
- Snapshot & signed audit chain (vulnerability snapshot manifest + audit log signatures)
- Correlation (planned) between anomalies and vulnerable assets

## ISO/IEC 27001 (Annex A) – Illustrative Links
- A.12 / A.8 (Asset & Operations security): SBOM + asset/component linkage provides up‑to‑date software asset context.
- A.12.6 (Technical vulnerability management): Automated ingestion of vulnerability intelligence (NVD/KEV/EPSS) and matching to environment components enables timely identification & risk assessment.
- A.5 (Organizational, context & responsibilities): Runtime parameter governance + audit signed changes show controlled configuration of vulnerability processes.
- A.8.16 / A.8.9 (Change & configuration management aspects): Versioned component inventory plus state transitions support controlled remediation tracking.

## NIST Cybersecurity Framework (CSF) Functions
- Identify (ID.AM, ID.RA): SBOM + asset mapping enumerates software assets; risk scoring contributes to risk assessment.
- Protect (PR.IP): Structured workflow & parameterized processes (e.g., enrichment refresh intervals) reflect protective process management.
- Detect (DE.CM): Continuous feed polling & enrichment act as monitoring for new exploitable conditions.
- Respond (RS.MI, RS.AN): Finding state transitions (open→triaged→fixed) and historical events support response & mitigation tracking.
- Recover (RC.IM): Signed snapshots provide integrity‑protected historical context for lessons learned / improvements.

## SOC 2 (Trust Services Criteria) – Relevant Themes
- Security (CC series): Automated identification of vulnerabilities & documented workflow evidences controls around change, monitoring, and risk identification.
- Change Management (CC8.x analog): Asset/component inventory tied to vulnerabilities supports assessing impact of changes & remediation prioritization.
- Risk Mitigation (CC9.x analog): Risk scoring blends exploitability + asset criticality to inform remediation prioritization.
- Logging & Integrity (CC6.x / CC7.x analog): Signed audit chains (audit log + snapshot) demonstrate tamper‑evident recording of key security-relevant events.

## Feature → Control Objective Traceability (Summary)
| Capability | Control Themes Supported |
|------------|--------------------------|
| SBOM ingestion & asset-component links | Asset inventory (ISO A.8, NIST ID.AM) |
| Vulnerability feed integration (NVD/KEV/EPSS) | Vulnerability identification (ISO A.12.6, NIST ID.RA) |
| Component→CVE matching | Timely detection of applicable vulns (ISO A.12.6, NIST DE.CM) |
| Risk scoring & prioritization | Risk assessment & mitigation (ISO A.12.6, NIST ID.RA, SOC2 CC9) |
| Finding state transitions & history | Workflow governance & response (NIST RS.MI, ISO A.5/A.12) |
| Signed audit & snapshot chain | Integrity & evidence (SOC2 CC6/CC7, NIST RC.IM) |
| Planned anomaly↔vuln correlation | Enhanced detection context (NIST DE.CM, RS.AN) |

## Roadmap Enhancements for Stronger Alignment
- Add SLA breach metrics & escalation events (supports response & accountability controls).
- Expand version range parsing for precise applicability (reducing false positives / improving risk accuracy).
- Enrich findings with remediation guidance provenance (supports procedural documentation controls).
- Add continuous verification tests of feed freshness & enrichment latency SLOs.

## Usage Guidance
This mapping is a facilitative aid. For audits or certification efforts:
1. Export signed vulnerability snapshots for the assessment period.
2. Provide audit log chain (with signature verification script output) to demonstrate integrity.
3. Show configuration parameter change history for vulnerability scanning cadence & risk weights.
4. Link remediation tickets to finding IDs (stable deterministic IDs derived from asset, component, CVE).

## Disclaimer
This file intentionally avoids quoting or reproducing normative control text. Always reference official publications for authoritative language and ensure professional judgment in interpreting control applicability.
