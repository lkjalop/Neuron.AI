# Vulnerability & Exposure Intelligence Overview (SOC Friendly)

Audience: Non-technical SOC analysts needing plain-language understanding of how Neuron handles software vulnerabilities and SBOM (Software Bill of Materials) data.

## 1. Why This Exists
Modern attacks often exploit known vulnerabilities faster than traditional patch cycles. We add continuous vulnerability intelligence so analysts can:
- See which issues matter most (risk-weighted)
- Know if an exploit is likely (EPSS probability, KEV catalog)
- Map vulnerabilities to affected assets/components (via SBOM)
- Track changes with audit integrity (tamper-resistant log)

## 2. Key Concepts (Plain Language)
| Term | Meaning | Analyst Action |
|------|---------|----------------|
| CVE | Public ID for a vulnerability (e.g., CVE-2025-1000) | Use it as a universal reference when escalating |
| OSV | Open Source Vulnerability entry (alternate ID) | Treated as alias; platform merges duplicates |
| EPSS | Probability a CVE will be exploited soon | High EPSS -> prioritize validation/patch |
| KEV | CISA catalog of actively exploited vulns | KEV listed -> treat as urgent |
| SBOM | Inventory of software components in an asset | Confirms exposure vs theoretical risk |
| Finding | A vulnerability actually present on one of YOUR assets/components | Active finding -> track to closure |
| Risk Score | Weighted 0..1 score combining severity + exploit context + asset criticality | Drives ordering of response queue |

## 3. Data Flow (Architecture in 6 Steps)
1. Feed Fetch: External sources (NVD, OSV) + enrichment (EPSS, KEV) are polled.
2. Normalize & Merge: Different formats converted to a unified vulnerability model; duplicates merged by CVE/alias.
3. Enrichment: Exploit probability (EPSS) and KEV presence applied. Exploit flags increase risk weight.
4. SBOM Ingest: You submit a CycloneDX document listing components for an asset. We record components and linkage.
5. Finding Creation: If a vulnerability's component aligns with an asset component, a finding is (or will be) created (initial demo uses synthetic findings; full matching to follow).
6. Risk Computation: Each finding is re-scored periodically using severity, exploit signals, and asset metadata (e.g., criticality).

Result: Analysts see a prioritized list of findings, not just raw CVEs.

## 4. IDs & Relationships (Mental Model)
```
Asset --(has components)--> Component --(may be affected by)--> Vulnerability (CVE)
      \                                                       /
       \---> Finding (joins Asset or Component to Vulnerability)
```
- Asset: A thing you operate (service, application, host). ID example: `asset-3fa9c1a2ef`.
- Component: A library/module from SBOM (e.g., `openssl:3.0.13`).
- Vulnerability: CVE-aligned record (severity + exploit context).
- Finding: Evidence that a vulnerability impacts you (ties CVE to asset/component + timestamps + risk score).

## 5. Risk Score (Simplified Explanation)
Ingredients:
- Base Severity (CVSS-like) -> mapped to baseline weight
- Exploit Signals -> EPSS probability curve + KEV/Exploit flags bonus up to configured cap
- Asset Criticality -> Provided in SBOM ingest metadata or defaults
- Time Factors -> (Future) aging / exposure time may increase urgency

Displayed Severity Labels: LOW, MEDIUM, HIGH, CRITICAL (mapped from normalized score thresholds).

## 6. What You Can Do Today
| Need | Endpoint | Notes |
|------|----------|-------|
| List vulnerabilities | `GET /vuln/vulnerabilities` | Filter by severity or exploit_only |
| List findings | `GET /vuln/findings` | Prioritized list (risk annotated) |
| Ingest SBOM | `POST /vuln/ingest_sbom` | Provide `asset_name` + CycloneDX `document` |

All are secured by the platform admin API key (and optional HMAC).

## 7. SBOM Ingestion (How-To)
Sample minimal body:
```json
{
  "asset_name": "checkout-service",
  "document": {
    "components": [
      {"name": "openssl", "version": "3.0.13", "purl": "pkg:openssl/openssl@3.0.13", "type": "library"},
      {"name": "flask", "version": "3.0.2", "purl": "pkg:pypi/flask@3.0.2", "type": "pypi"}
    ]
  },
  "asset_metadata": {"criticality": 0.9}
}
```
Response includes assigned `asset_id` and persisted components.

## 8. Exploit Intelligence Signals
| Signal | Source | Meaning |
|--------|--------|---------|
| `exploit_available` | Heuristic now; later real exploit kit sources | Known exploit in-the-wild indicators |
| `epss` | EPSS feed (probability 0..1) | Likelihood of exploitation soon |
| `kev_listed` | CISA KEV catalog | Actively exploited; high priority |

## 9. Integrity & Audit
- All parameter changes and governance events land in `audit/AUDIT_LOG.md`.
- Signatures (HMAC now, stronger crypto future) record log state to detect tampering.
- Canonical documentation hash prevents silent drift of operational doctrine.

## 10. Roadmap (Analyst-Relevant Highlights)
| Upcoming | Analyst Benefit |
|----------|-----------------|
| Real component-to-CVE matching | Findings reflect true exposure, not just synthetic linking |
| Exploit kit feed integration | Earlier awareness of weaponized flaws |
| SLA timers & state transitions | Triage workflow & overdue highlighting |
| Correlation with anomaly spikes | Combined behavioral + vulnerability narratives |
| Stronger cryptographic log chain | Higher confidence in evidence chain |

## 11. Quick FAQ
Q: Why do I see vulnerabilities but no findings yet?  
A: Either SBOM not ingested or matching logic not triggered; synthetic findings used initially for demonstration.  
Q: Does a high EPSS always mean we are impacted?  
A: No. Impact requires a finding (confirmed component present). EPSS helps prioritize investigation.  
Q: How often does data refresh?  
A: Scanner loop interval is configurable via `vuln.scan.interval_seconds` (default hourly placeholder).  

## 12. Minimal Triage Checklist
1. Pull `/vuln/findings` sorted by risk (already prioritized).  
2. Filter for `kev_listed == true` OR `epss > 0.5`.  
3. Confirm asset criticality from metadata.  
4. Escalate HIGH/CRITICAL with KEV or high EPSS.  
5. Track closure state (future: state transition endpoints).  

---
This document is eligible for ingestion into the internal RAG knowledge base. Keep language simple for broader SOC adoption.
