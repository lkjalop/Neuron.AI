"""Component -> Vulnerability matcher.

Scans persisted components and vulnerabilities, applies rudimentary matching
logic using alias/product name heuristics and optional CPE version range data
embedded in vulnerability raw_json (if present) to create findings.

Scope (initial):
 - For each vulnerability, attempt to match components where component name
   appears in vulnerability raw_json['raw_json']['cve']['references'] or alias list (simplified placeholder).
 - If vulnerability raw_json contains a 'cpe_matches' array (pre-normalized list
   of NVD cpeMatch dicts), apply version gating via any_cpe_match_applies.
 - Upsert finding with deterministic id f"find-{component_id}-{cve_id}".

Future improvements: real CPE product/vendor mapping, PURL ecosystem mapping,
semantic version diff scoring, batch SQL joins.
"""
from __future__ import annotations

import time, json
from typing import Dict, Any, List

from scanner.version_applicability import any_cpe_match_applies  # type: ignore
from storage import postgres  # type: ignore
from storage import vuln_store  # type: ignore


async def _fetch_components() -> List[Dict[str, Any]]:
    rows = await postgres.fetch("SELECT id, name, version, purl, ecosystem FROM sbom_components")
    return [dict(r) for r in rows]


async def _fetch_vulns(limit: int = 5000) -> List[Dict[str, Any]]:
    rows = await postgres.fetch("SELECT cve_id, aliases, raw_json FROM vulnerabilities LIMIT $1", limit)
    vulns = []
    for r in rows:
        raw = r["raw_json"]
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = {}
        vulns.append({
            "cve_id": r["cve_id"],
            "aliases": r.get("aliases") or [],
            "raw": raw,
        })
    return vulns


def _extract_cpe_matches(vraw: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Expect pre-parsed list under key 'cpe_matches' OR attempt to walk NVD style nodes.
    if "cpe_matches" in vraw:
        return vraw.get("cpe_matches") or []
    # Shallow walk for NVD configurations
    conf = vraw.get("configurations") or {}
    nodes = conf.get("nodes") or []
    matches: List[Dict[str, Any]] = []
    for n in nodes:
        for cm in n.get("cpeMatch", []):
            matches.append(cm)
    return matches


async def run_component_match(max_vulns: int = 1000) -> Dict[str, Any]:
    components = await _fetch_components()
    vulns = await _fetch_vulns(limit=max_vulns)
    created = 0
    scanned_pairs = 0
    now = time.time()
    comp_index = {c["name"].lower(): c for c in components if c.get("name")}
    for v in vulns:
        cpe_matches = _extract_cpe_matches(v["raw"])
        aliases = [a.lower() for a in (v.get("aliases") or [])]
        # Heuristic: match component if name appears in aliases OR simple substring
        for cname, comp in comp_index.items():
            scanned_pairs += 1
            if aliases and not any(cname in a or a in cname for a in aliases):
                continue
            # Version applicability gating if cpe data present
            if cpe_matches:
                if not any_cpe_match_applies(cpe_matches, comp.get("version")):
                    continue
            fid = f"find-{comp['id']}-{v['cve_id']}"
            try:
                await vuln_store.upsert_finding({  # type: ignore[attr-defined]
                    "id": fid,
                    "cve_id": v["cve_id"],
                    "asset_id": None,  # future: derive from asset_components join
                    "component_id": comp["id"],
                    "first_seen": now,
                    "last_seen": now,
                    "state": "open",
                    "detection_source": "match",
                    "risk_score": None,
                    "risk_severity": None,
                    "asset_metadata": {},
                })
                created += 1
            except Exception:
                continue
    return {"components": len(components), "vulns": len(vulns), "created_findings": created, "pairs_scanned": scanned_pairs}

__all__ = ["run_component_match"]
