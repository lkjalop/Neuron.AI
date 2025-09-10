# Compliance & Governance Tracking

| Framework | Domain / Control | Artifact / Module | Status | Evidence Source | Notes |
|-----------|------------------|-------------------|--------|-----------------|-------|
| SOC 2 | Change Management | audit/AUDIT_LOG.md | Planned | Git history | Establish process gates |
| SOC 2 | Security Monitoring | (metrics subsystem) | Planned | Prometheus metrics | To implement Phase 1.5 |
| ISO 27001 | A.12 Operations Security | Future ops runbook | Planned | docs/ (pending) | Reuse prior runbook draft |
| ISO 27001 | A.9 Access Control | src/iam/ | Planned | IAM tests | RBAC + ABAC scaffolding |
| NIST CSF | DE.AE-1 Anomaly Detection | SNN + baseline detectors | Planned | Evaluation reports | Need calibration harness |
| NIST AI RMF | Measure - Performance | evaluation scripts | Planned | eval JSON | Add calibration metrics |
| ISO 42001 | Transparency | agent reasoning logs | Planned | reasoning store | LLM disabled initially |
| EU AI Act | Human Oversight | docs/CENTRAL_DOGMA.md | Partial | Policy doc | Add override workflow |
| MITRE ATT&CK | Technique Mapping | future enrichment | Idea | TBD | Build mapping table |
| SLSA | Build Provenance | scripts/manifest + future CI | Idea | Manifest chain | Cosign later |

Legend: Planned | Partial | Implemented | Idea

Advisory References:
- A01 (2025-09-02): Initial architecture & compliance roadmap captured externally.

Change Procedure: Update table rows only via appended audit log entry referencing the change.
