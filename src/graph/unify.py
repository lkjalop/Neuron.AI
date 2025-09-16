"""Graph Unification Utilities.

Purpose: Merge the vulnerability-centric `ExposureGraph` into the generic
`RelationshipGraph` so higher-level analytics (features, link prediction)
can reason over a single cohesive topology.

Mapping Strategy:
  Exposure Nodes:
    asset:<id>        -> asset:<id>
    component:<id>    -> component:<id>
    vuln:<cve>        -> vuln:<cve>
    technique:<t>     -> technique:<t>
    control:<id>      -> control:<id>
  Exposure Edges (type -> rel_type maintained as-is with prefix):
    asset-component   -> exposure:asset_component
    component-vuln    -> exposure:component_vuln
    vuln-technique    -> exposure:vuln_technique
    control-technique -> exposure:control_technique

Edge rel_type names are prefixed with `exposure:` to avoid collision with
semantic detection edges (resolves_to, authenticates_to, etc.).

Idempotency: Multiple calls will append duplicate edges presently; future
optimization could add a de-duplication set. Acceptable for prototype.
"""
from __future__ import annotations

from typing import Any, Dict

from .relationships import get_graph


EXPOSURE_EDGE_TYPE_MAP = {
    "asset-component": "exposure:asset_component",
    "component-vuln": "exposure:component_vuln",
    "vuln-technique": "exposure:vuln_technique",
    "control-technique": "exposure:control_technique",
}


async def ingest_exposure_snapshot(snapshot: Dict[str, Any]):
    """Ingest an ExposureGraph snapshot (dict form) into RelationshipGraph.

    Expected snapshot keys: nodes (list), edges (list with src,dst,type)
    """
    g = get_graph()
    edges = snapshot.get("edges", [])
    for e in edges:
        etype = e.get("type")
        mapped = EXPOSURE_EDGE_TYPE_MAP.get(etype)
        if not mapped:
            continue
        src = e.get("src")
        dst = e.get("dst")
        if not src or not dst:
            continue
        # Metadata can carry through severity / exploitability if present on nodes later.
        await g.add_edge(src, dst, rel_type=mapped, weight=1.0, metadata={"source": "exposure_graph"})


__all__ = ["ingest_exposure_snapshot", "EXPOSURE_EDGE_TYPE_MAP"]
