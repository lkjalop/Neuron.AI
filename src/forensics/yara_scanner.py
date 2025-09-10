"""YARA scanner wrapper (behind runtime flag).

Provides a small helper to compile a rule set and scan a list of file paths.
Findings are transformed into evidence artifacts with basic severity tags.

Design goals:
- Graceful degradation if `yara` is not installed.
- Conservative time limits and result sizes; caller controls runtime budget.
- Portable: avoid OS-specific dependencies; rules_dir may be empty.

API:
- scan(paths: list[str], rules_dir: str | None, max_runtime_s: float = 30.0) -> dict
  Returns: {"artifacts": [..], "summary": {"files_scanned": int, "matches": int, "errors": {..}}}
"""
from __future__ import annotations

from typing import List, Dict, Any
import os, time


def _severity_from_yara(rule_name: str, tags: List[str] | None) -> str:
    name = (rule_name or "").lower()
    tagset = {t.lower() for t in (tags or [])}
    # Simple heuristics: names or tags indicating higher risk
    if any(k in name for k in ["mimikatz", "cobalt", "meterpreter", "c2", "ransom"]):
        return "high"
    if {"high", "critical"} & tagset:
        return "high"
    if {"medium", "suspicious"} & tagset:
        return "medium"
    return "low"


def scan(paths: List[str], rules_dir: str | None, max_runtime_s: float = 30.0) -> Dict[str, Any]:
    artifacts: List[Dict[str, Any]] = []
    errors: Dict[str, str] = {}
    files_scanned = 0
    try:
        import yara  # type: ignore
    except Exception as e:  # pragma: no cover - optional dependency
        return {
            "artifacts": [],
            "summary": {
                "files_scanned": 0,
                "matches": 0,
                "errors": {"import": f"yara_unavailable:{e}"},
            },
        }

    # Build rules compilation filemap from directory
    rules = None
    try:
        filepaths: Dict[str, str] = {}
        if rules_dir and os.path.isdir(rules_dir):
            for root, _dirs, files in os.walk(rules_dir):
                for fn in files:
                    if fn.lower().endswith((".yar", ".yara")):
                        path = os.path.join(root, fn)
                        filepaths[fn] = path
        if filepaths:
            rules = yara.compile(filepaths=filepaths)  # type: ignore[attr-defined]
        else:
            # Empty rules means no matches; return quickly
            return {
                "artifacts": [],
                "summary": {"files_scanned": 0, "matches": 0, "errors": {"rules": "no_rules_found"}},
            }
    except Exception as e:
        return {
            "artifacts": [],
            "summary": {"files_scanned": 0, "matches": 0, "errors": {"compile": str(e)}},
        }

    start = time.time()
    deadline = start + max(1.0, float(max_runtime_s))
    for p in paths or []:
        if time.time() >= deadline:
            errors["timeout"] = "budget_exhausted"
            break
        try:
            # Skip non-files
            if not os.path.isfile(p):
                continue
            files_scanned += 1
            matches = rules.match(p)  # type: ignore[call-arg]
            for m in matches:
                art = {
                    "type": "yara.match",
                    "data": {
                        "rule": getattr(m, "rule", None),
                        "namespace": getattr(m, "namespace", None),
                        "tags": list(getattr(m, "tags", []) or []),
                        # strings: list of (offset, identifier, data)
                        "strings": [
                            {
                                "offset": s[0],
                                "id": s[1],
                                "value": s[2].decode("latin-1", errors="ignore") if isinstance(s[2], (bytes, bytearray)) else str(s[2])[:200],
                            }
                            for s in list(getattr(m, "strings", []) or [])[:10]
                        ],
                        "filepath": p,
                    },
                    "severity": _severity_from_yara(getattr(m, "rule", ""), list(getattr(m, "tags", []) or [])),
                    "source": "yara",
                }
                artifacts.append(art)
        except Exception as e:
            errors[p] = str(e)[:500]

    return {
        "artifacts": artifacts,
        "summary": {"files_scanned": files_scanned, "matches": len(artifacts), "errors": errors},
    }


__all__ = ["scan"]
