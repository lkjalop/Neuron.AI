"""Attack path graph builder (simplified).

Derives 3-hop paths: Asset -> Component -> Vulnerability (Finding) from
persistence and assigns a basic path risk score.

Scoring heuristic (initial): max finding risk score on component * (1 + emergence_p_avg).
Future expansions: exploit chain probability, exposure weighting, lateral movement edges.
"""
from __future__ import annotations

from typing import List, Dict, Any
import json

from storage import postgres  # type: ignore


async def build_paths(limit: int = 50) -> List[Dict[str, Any]]:
    # Join assets -> asset_components -> sbom_components -> findings -> vulnerabilities
    rows = await postgres.fetch(
        """
        SELECT a.id AS asset_id, a.name AS asset_name, a.external_exposure,
               c.id AS component_id, c.name AS component_name, c.ecosystem,
               f.id AS finding_id, f.risk_score, f.risk_factors, f.risk_severity, f.cve_id,
               v.severity AS vuln_severity
        FROM assets a
        JOIN asset_components ac ON ac.asset_id = a.id
        JOIN sbom_components c ON c.id = ac.component_id
        JOIN findings f ON f.component_id = c.id
        JOIN vulnerabilities v ON v.cve_id = f.cve_id
        ORDER BY f.risk_score DESC NULLS LAST
        LIMIT $1
        """,
        limit * 3,  # over-fetch then trim after grouping
    )
    paths: List[Dict[str, Any]] = []
    for r in rows:
        rf = r["risk_factors"]
        if isinstance(rf, str):
            try:
                rf = json.loads(rf)
            except Exception:
                rf = {}
        emergence = (rf or {}).get("emergence_p") or 0.0
        path_risk = (r["risk_score"] or 0.0) * (1.0 + emergence)
        paths.append({
            "asset": {
                "id": r["asset_id"],
                "name": r["asset_name"],
                "external_exposure": r["external_exposure"],
            },
            "component": {
                "id": r["component_id"],
                "name": r["component_name"],
                "ecosystem": r["ecosystem"],
            },
            "finding": {
                "id": r["finding_id"],
                "cve_id": r["cve_id"],
                "risk_score": r["risk_score"],
                "risk_severity": r["risk_severity"],
                "emergence_p": emergence,
            },
            "path_risk": path_risk,
        })
    # Deduplicate by finding id worst-first
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for p in sorted(paths, key=lambda x: x["path_risk"], reverse=True):
        fid = p["finding"]["id"]
        if fid in seen:
            continue
        seen.add(fid)
        deduped.append(p)
        if len(deduped) >= limit:
            break
    return deduped

__all__ = ["build_paths"]
