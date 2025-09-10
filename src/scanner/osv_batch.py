"""OSV bulk query helper.

Provides a minimal batch query client for OSV's /v1/querybatch endpoint.
We only need package name + ecosystem queries for alias expansion (no version
filtering yet). Cache results in-memory for current process.
"""
from __future__ import annotations

import aiohttp, asyncio, time
from typing import Dict, Any, List

_OSV_CACHE: Dict[str, Dict[str, Any]] = {}
_OSV_LAST_FETCH = 0.0

API_URL = "https://api.osv.dev/v1/querybatch"

async def fetch_osv_aliases(components: List[tuple[str, str]], force: bool = False) -> Dict[str, List[str]]:
    """Fetch OSV entries for a list of (name, ecosystem) components.

    Returns mapping of cve_id -> aliases (including original IDs) aggregated across results.
    Basic rate limiting: avoid more than one call per 300s unless force.
    """
    global _OSV_LAST_FETCH
    now = time.time()
    if not force and (now - _OSV_LAST_FETCH) < 300 and _OSV_CACHE:
        # Derive alias map from cached vulnerabilities
        alias_map: Dict[str, List[str]] = {}
        for vid, rec in _OSV_CACHE.items():
            aliases = rec.get("aliases") or []
            alias_map[vid] = list(set([vid] + aliases))
        return alias_map
    queries = []
    for name, eco in components:
        if not name or not eco:
            continue
        queries.append({"package": {"name": name, "ecosystem": eco}})
    if not queries:
        return {}
    payload = {"queries": queries}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, json=payload, timeout=30) as resp:
                if resp.status != 200:
                    return {}
                data = await resp.json()
    except Exception:
        return {}
    results = data.get("results", []) if isinstance(data, dict) else []
    alias_map: Dict[str, List[str]] = {}
    for r in results:
        vulns = r.get("vulns") or []
        for v in vulns:
            vid = v.get("id")
            if not vid:
                continue
            _OSV_CACHE[vid] = v
            aliases = v.get("aliases") or []
            alias_map[vid] = list(set([vid] + aliases))
    _OSV_LAST_FETCH = now
    return alias_map

__all__ = ["fetch_osv_aliases"]
