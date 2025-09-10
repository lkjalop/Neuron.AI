"""Local vulnerability catalog loader (offline seed).

Loads a small JSON seed file with entries:
  package: str (lowercase)
  affected: str (simple operator form: <=version, <version, =version, or plain exact)
  cve: str
  severity: str (HIGH/MEDIUM/LOW/CRITICAL)
  cvss_base: float (optional)

Future extension: support semantic ranges, NVD/OSV ingestion.
"""
from __future__ import annotations
import json, re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

SEED_PATH = Path("artifacts/vuln_catalog_seed.json")
_VERSION_RE = re.compile(r"^(<=|<|=)?\s*([0-9]+\.[0-9]+\.[0-9]+)")

_CATALOG: List[Dict[str, Any]] = []


def _parse_version(v: str) -> Tuple[int,int,int]:
    parts = v.split('.')
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except Exception:
        return (0,0,0)


def _version_cmp(a: str, b: str) -> int:
    return ( (_parse_version(a) > _parse_version(b)) - (_parse_version(a) < _parse_version(b)) )


def _match_affected(spec: str, version: str) -> bool:
    m = _VERSION_RE.match(spec.strip())
    if not m:
        # treat as exact
        return spec.strip() == version
    op, ver = m.group(1), m.group(2)
    if not op or op == '=':
        return version == ver
    cmp = _version_cmp(version, ver)
    if op == '<=':
        return cmp <= 0
    if op == '<':
        return cmp < 0
    return False


def load_catalog(force: bool = False) -> List[Dict[str, Any]]:
    global _CATALOG
    if _CATALOG and not force:
        return _CATALOG
    if not SEED_PATH.exists():
        _CATALOG = []
        return _CATALOG
    try:
        data = json.loads(SEED_PATH.read_text(encoding='utf-8'))
        if isinstance(data, list):
            # normalize
            norm = []
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                pkg = str(entry.get('package') or '').lower().strip()
                if not pkg:
                    continue
                aff = str(entry.get('affected') or '').strip()
                cve = str(entry.get('cve') or '').strip()
                sev = str(entry.get('severity') or 'UNKNOWN').upper()
                cvss = entry.get('cvss_base')
                norm.append({
                    'package': pkg,
                    'affected': aff,
                    'cve': cve,
                    'severity': sev,
                    'cvss_base': cvss,
                })
            _CATALOG = norm
        else:
            _CATALOG = []
    except Exception:
        _CATALOG = []
    return _CATALOG


def find_matches(components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cat = load_catalog()
    matches: List[Dict[str, Any]] = []
    if not cat or not components:
        return matches
    for comp in components:
        name = str(comp.get('name') or '').lower().strip()
        version = str(comp.get('version') or '').strip()
        if not name or not version:
            continue
        for entry in cat:
            if entry['package'] != name:
                continue
            if entry['affected'] and _match_affected(entry['affected'], version):
                out = dict(entry)
                out['component'] = name
                out['component_version'] = version
                out['asset_metadata'] = comp.get('asset_metadata') or comp.get('metadata') or {}
                matches.append(out)
    return matches

__all__ = ["load_catalog", "find_matches"]
