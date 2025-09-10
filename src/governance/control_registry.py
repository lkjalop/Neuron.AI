"""Control Coverage Registry

Provides a static, declarative mapping between internal platform capabilities
and external control frameworks (NIST CSF, NIST 800-53, CIS/SANS Top 18 / CSC,
ISO style placeholders). This is *metadata only* – no persistence required.

Each feature entry enumerates:
 - id: internal stable identifier
 - name: human readable label
 - category: coarse functional grouping
 - description: short purpose summary
 - controls: list of external control references
 - evidence: which subsystem(s) can emit supporting evidence (future hook)

The registry is intentionally concise; downstream reporting APIs can perform
aggregation (e.g., coverage % of a framework) without needing a database table.
"""
from __future__ import annotations

from typing import Dict, List, Any


_REGISTRY: List[Dict[str, Any]] = [
    {
        "id": "ingest.event_pipeline",
        "name": "Event Ingestion & Normalization",
        "category": "Ingest",
        "description": "Structured intake, validation, and normalization of security & telemetry events.",
        "controls": [
            "NIST-CSF:DE.AE-1",  # Anomalies and events are detected
            "NIST-800-53:AU-6",  # Audit Review
            "CIS-18:08.2",       # Centralize log management
        ],
        "evidence": ["pipeline", "anomaly_buffer"],
    },
    {
        "id": "detect.multi_engine_fusion",
        "name": "Multi-Engine Detection Fusion",
        "category": "Detection",
        "description": "Correlates baseline, SNN, and heuristic detectors with fusion arbitration.",
        "controls": [
            "NIST-CSF:DE.DP-4",  # detection processes are continually improved
            "NIST-800-53:SI-4",  # System Monitoring
            "CIS-18:08.5",
        ],
        "evidence": ["fusion", "metrics"],
    },
    {
        "id": "vuln.scanning_core",
        "name": "Vulnerability Feed Aggregation",
        "category": "Vulnerability",
        "description": "Aggregates NVD/OSV & enriches with EPSS, KEV & alias expansion.",
        "controls": [
            "NIST-CSF:ID.RA-1",  # Asset vulnerabilities identified
            "NIST-800-53:RA-5",  # Vulnerability Scanning
            "CIS-18:07.6",
        ],
        "evidence": ["feed_state", "vulnerabilities"],
    },
    {
        "id": "vuln.risk_scoring_predictive",
        "name": "Predictive Risk Scoring",
        "category": "Vulnerability",
        "description": "Combines static + temporal + reservoir + drift signals into emergence probability.",
        "controls": [
            "NIST-CSF:ID.RA-2",
            "NIST-800-53:PM-16",  # Threat Awareness
            "CIS-18:07.7",
        ],
        "evidence": ["findings.risk_factors"],
    },
    {
        "id": "governance.sla_tracking",
        "name": "SLA Breach Tracking",
        "category": "Governance",
        "description": "Assigns & monitors remediation due dates for findings.",
        "controls": [
            "NIST-CSF:RS.MI-1",  # Incidents contained
            "NIST-800-53:IR-4",
            "CIS-18:17.6",
        ],
        "evidence": ["findings.sla_due_ts"],
    },
    {
        "id": "governance.exceptions_workflow",
        "name": "Risk Acceptance & Exceptions",
        "category": "Governance",
        "description": "Lifecycle for temporary acceptance / exception events with audit trail.",
        "controls": [
            "NIST-CSF:ID.RA-3",
            "NIST-800-53:RA-7",  # Risk Response
            "CIS-18:16.13",
        ],
        "evidence": ["exceptions", "exception_events"],
    },
    {
        "id": "framework.attack_mapping",
        "name": "ATT&CK Mapping",
        "category": "Intelligence",
        "description": "Relates vulnerabilities and software to ATT&CK techniques for context.",
        "controls": [
            "NIST-CSF:DE.CM-1",
            "NIST-800-53:CA-2",  # Security Assessments (contextual mapping support)
        ],
        "evidence": ["attack_techniques", "vuln_software_map"],
    },
    {
        "id": "exposure.asset_flagging",
        "name": "Asset Exposure Classification",
        "category": "Inventory",
        "description": "Differentiates external vs internal assets for prioritization weighting.",
        "controls": [
            "NIST-CSF:ID.AM-1",
            "NIST-800-53:CM-8",  # Information System Components
            "CIS-18:01.1",
        ],
        "evidence": ["assets.external_exposure"],
    },
]


def list_controls() -> Dict[str, Any]:
    return {"count": len(_REGISTRY), "items": _REGISTRY}


def framework_coverage(framework_prefix: str) -> Dict[str, Any]:
    matched = [r for r in _REGISTRY if any(c.startswith(framework_prefix) for c in r["controls"])]
    # Unique controls referenced
    controls = sorted({c for r in matched for c in r["controls"] if c.startswith(framework_prefix)})
    return {
        "framework_prefix": framework_prefix,
        "feature_count": len(matched),
        "unique_controls": controls,
    }


__all__ = ["list_controls", "framework_coverage"]
