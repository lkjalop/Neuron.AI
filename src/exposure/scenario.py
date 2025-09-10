"""Exposure Scenario Simulation (Batch 21).

Allows hypothetical changes to controls or vulnerabilities to assess exposure delta.

Input mutations examples:
  {"action":"remove_control", "id":"C123"}
  {"action":"add_vuln", "cve":"CVE-2024-9999", "severity":"HIGH", "asset_id":"asset-1"}

Return structure:
  {
    "baseline_total_risk": float,
    "simulated_total_risk": float,
    "delta": float,
    "added": [...],
    "removed_controls": [...]
  }
"""
from __future__ import annotations
from typing import List, Dict, Any
import copy, time

from .graph import ExposureGraph, build_graph


def simulate(
    baseline_graph: ExposureGraph,
    mutations: List[Dict[str, Any]]
) -> Dict[str, Any]:
    # Clone minimal data needed
    findings = []
    controls = []
    for n in baseline_graph.nodes.values():
        if n.type == "vuln":
            # reconstruct finding stub
            cve = n.id.split(":",1)[1]
            findings.append({
                "cve_id": cve,
                "risk_score": n.data.get("base_risk"),
                "risk_severity": n.data.get("severity"),
                "first_seen": time.time() - n.data.get("age_days", 0)*86400,
            })
        elif n.type == "control":
            cid = n.id.split(":",1)[1]
            # Techniques via edges
            techs = [e.dst.split(":",1)[1] for e in baseline_graph.edges if e.src == n.id and e.type == "control-technique"]
            controls.append({"id": cid, "techniques": techs})
    removed_controls = []
    added_findings = []
    for m in mutations:
        act = m.get("action")
        if act == "remove_control":
            cid = m.get("id")
            controls = [c for c in controls if c.get("id") != cid]
            removed_controls.append(cid)
        elif act == "add_vuln":
            cve = m.get("cve")
            if cve:
                added_findings.append(cve)
                findings.append({
                    "cve_id": cve,
                    "risk_severity": m.get("severity", "MEDIUM"),
                    "risk_score": m.get("risk_score"),
                    "first_seen": time.time(),
                    "asset_id": m.get("asset_id"),
                    "component_id": m.get("component_id"),
                })
    sim_graph = build_graph(findings, controls)
    return {
        "baseline_total_risk": baseline_graph.total_risk,
        "simulated_total_risk": sim_graph.total_risk,
        "delta": sim_graph.total_risk - baseline_graph.total_risk,
        "added_vulns": added_findings,
        "removed_controls": removed_controls,
    }

__all__ = ["simulate"]