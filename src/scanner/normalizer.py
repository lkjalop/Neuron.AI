from __future__ import annotations
import hashlib
from typing import Iterable, Dict, Any, List
from datetime import datetime
from .models import Vulnerability


def _hash_id(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
    return h.hexdigest()[:32]

def _parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z","+00:00"))
    except Exception:
        return None

def normalize_nvd(item: Dict[str, Any]) -> Vulnerability:
    cve_id = item.get("cve", {}).get("id") or item.get("cve", {}).get("CVE_data_meta", {}).get("ID") or item.get("id")
    metrics = item.get("metrics", {})
    base_score = None
    vector = None
    severity = None
    if isinstance(metrics, dict):
        if "cvssMetricV31" in metrics:
            try:
                m = metrics["cvssMetricV31"][0]["cvssData"]
                base_score = m.get("baseScore")
                vector = m.get("vectorString")
                severity = metrics["cvssMetricV31"][0].get("baseSeverity")
            except Exception:
                pass
    aliases = list({cve_id}) if cve_id else []
    cwe_ids: List[str] = []
    for prob in item.get("weaknesses", []):
        for d in prob.get("description", []):
            val = d.get("value")
            if isinstance(val, str) and val.startswith("CWE-"):
                cwe_ids.append(val)
    return Vulnerability(
        id=_hash_id("nvd", cve_id or "unknown"),
        cve_id=cve_id or "UNKNOWN",
        aliases=aliases,
        cvss_base=base_score,
        cvss_vector=vector,
        severity=severity,
        cwe_ids=cwe_ids,
        published_ts=_parse_dt(item.get("published")),
        modified_ts=_parse_dt(item.get("lastModified")),
        exploit_available=False,
        epss=None,
        kev_listed=False,
        raw_json=item,
    )

def normalize_osv(entry: Dict[str, Any]) -> Vulnerability:
    aliases: List[str] = []
    cve_id = None
    for alias in entry.get("aliases", []):
        aliases.append(alias)
        if alias.startswith("CVE-"):
            cve_id = alias
    cve_id = cve_id or entry.get("id") or "UNKNOWN"
    return Vulnerability(
        id=_hash_id("osv", cve_id),
        cve_id=cve_id,
        aliases=list(set(aliases + [cve_id])),
        cvss_base=None,
        cvss_vector=None,
        severity=None,
        cwe_ids=[],
        published_ts=_parse_dt(entry.get("published")),
        modified_ts=_parse_dt(entry.get("modified")),
        exploit_available=False,
        epss=None,
        kev_listed=False,
        raw_json=entry,
    )

def merge_vulnerabilities(vulns: Iterable[Vulnerability]) -> Dict[str, Vulnerability]:
    merged: Dict[str, Vulnerability] = {}
    for v in vulns:
        key = v.cve_id
        if key not in merged:
            merged[key] = v
        else:
            existing = merged[key]
            # Precedence: keep first non-null cvss_base
            if existing.cvss_base is None and v.cvss_base is not None:
                existing.cvss_base = v.cvss_base
                existing.cvss_vector = v.cvss_vector
            existing.aliases = list(set(existing.aliases + v.aliases))
            existing.raw_json.setdefault("sources", []).append(v.raw_json)
    return merged

__all__ = [
    "normalize_nvd","normalize_osv","merge_vulnerabilities"
]
