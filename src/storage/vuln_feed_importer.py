from __future__ import annotations

"""Vulnerability feed importer (seed files -> vulnerabilities table).

Supports two input formats (autodetected by extension):
 - JSON: either an array of vulnerability dicts or object with key "items".
 - CSV: columns include cve_id, severity, aliases (semicolon or comma separated), epss, exploit_available, kev_listed.

Paths searched (in order):
 - artifacts/vuln_catalog_seed.json
 - artifacts/vuln_catalog_enhanced.json
 - dump/vulns.json, dump/vulns.csv

Only a subset of fields are required; missing fields are defaulted.
"""

import json, csv, os
from typing import List, Dict, Any, Tuple
from datetime import datetime

from scanner.models import Vulnerability  # type: ignore
from . import vuln_store

SEED_PATHS = [
    "artifacts/vuln_catalog_seed.json",
    "artifacts/vuln_catalog_enhanced.json",
    "dump/vulns.json",
    "dump/vulns.csv",
]


def _coerce_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in {"1", "true", "yes", "y", "on"}


def _to_dt(ts: Any) -> datetime | None:
    try:
        if ts is None:
            return None
        if isinstance(ts, (int, float)):
            return datetime.utcfromtimestamp(float(ts))
        s = str(ts).strip()
        # Try ISO-like
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


async def import_from_records(records: List[Dict[str, Any]]) -> int:
    vulns: List[Vulnerability] = []
    for r in records:
        try:
            cve_id = r.get("cve_id") or r.get("id") or r.get("CVE")
            if not cve_id:
                continue
            aliases = r.get("aliases") or []
            if isinstance(aliases, str):
                aliases = [a.strip() for a in aliases.replace(";", ",").split(",") if a.strip()]
            vulns.append(Vulnerability(
                id=cve_id,
                cve_id=cve_id,
                aliases=aliases,
                cvss_base=(float(r.get("cvss_base")) if r.get("cvss_base") else None),
                cvss_vector=r.get("cvss_vector"),
                severity=(r.get("severity") or "MEDIUM").upper(),
                cwe_ids=r.get("cwe_ids") or [],
                published_ts=_to_dt(r.get("published_ts")),
                modified_ts=_to_dt(r.get("modified_ts")) or _to_dt(r.get("updated")),
                exploit_available=_coerce_bool(r.get("exploit_available") or False),
                epss=(float(r.get("epss")) if r.get("epss") not in (None, "") else None),
                kev_listed=_coerce_bool(r.get("kev_listed") or r.get("kev") or False),
                raw_json=r,
            ))
        except Exception:
            continue
    if not vulns:
        return 0
    return await vuln_store.upsert_vulnerabilities(vulns)


async def import_from_file(path: str) -> Tuple[int, str]:
    if not os.path.exists(path):
        return 0, "not_found"
    try:
        if path.lower().endswith(".json"):
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            records = obj if isinstance(obj, list) else obj.get("items", [])
            n = await import_from_records(records or [])
            return n, "json"
        if path.lower().endswith(".csv"):
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                records = list(reader)
            n = await import_from_records(records)
            return n, "csv"
    except Exception as e:  # noqa: BLE001
        return 0, f"error:{e}"
    return 0, "unsupported"


async def import_seed() -> Dict[str, Any]:
    """Try a series of default seed paths and import the first that exists."""
    tried: List[str] = []
    for p in SEED_PATHS:
        tried.append(p)
        if os.path.exists(p):
            n, kind = await import_from_file(p)
            return {"imported": n, "kind": kind, "path": p}
    return {"imported": 0, "kind": "none", "tried": tried}


__all__ = ["import_seed", "import_from_file", "import_from_records"]