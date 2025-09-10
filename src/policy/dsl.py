"""Policy DSL loader for compliance automation (Batch 19).

Supports YAML or JSON documents with schema:
{
  "version": 1,
  "id": "policy-main",
  "allowed_adjust_range": {"detection.temporal.weight": [0.05, 0.25]},
  "min_coverage_by_class": {"MITRE.TA0001": 0.6, "MITRE.TA0002": 0.5},
  "required_techniques": ["T1003", "T1047"],
  "exceptions": [
     {"id": "ex1", "technique": "T1003", "reason": "legacy system", "expires": 1750000000}
  ]
}
"""
from __future__ import annotations
from typing import Any, Dict, List
import json, time, os
from pathlib import Path

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

_POLICY_CACHE: Dict[str, Dict[str, Any]] = {}

REQUIRED_TOP_LEVEL = {"version", "id"}

class PolicyError(Exception):
    pass

def _parse_raw(raw: str, source: str) -> Dict[str, Any]:
    # attempt JSON first
    try:
        return json.loads(raw)
    except Exception:
        if yaml:
            try:
                return yaml.safe_load(raw)  # type: ignore
            except Exception as e:
                raise PolicyError(f"failed_parse:{source}:{e}")
    raise PolicyError(f"unrecognized_format:{source}")


def load_policy(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise PolicyError("file_not_found")
    raw = p.read_text(encoding="utf-8")
    data = _parse_raw(raw, str(p))
    if not isinstance(data, dict):
        raise PolicyError("root_not_object")
    missing = REQUIRED_TOP_LEVEL - set(data.keys())
    if missing:
        raise PolicyError(f"missing_keys:{','.join(sorted(missing))}")
    # Normalize shapes
    data.setdefault("allowed_adjust_range", {})
    data.setdefault("min_coverage_by_class", {})
    data.setdefault("required_techniques", [])
    data.setdefault("exceptions", [])
    if not isinstance(data["exceptions"], list):
        raise PolicyError("invalid_exceptions")
    _POLICY_CACHE[data["id"]] = data
    return data


def get_policy(pid: str) -> Dict[str, Any] | None:
    return _POLICY_CACHE.get(pid)


def list_policies() -> List[Dict[str, Any]]:
    return list(_POLICY_CACHE.values())


def active_exceptions(policy: Dict[str, Any], now: float | None = None) -> List[Dict[str, Any]]:
    now = now or time.time()
    out = []
    for ex in policy.get("exceptions", []):
        if not isinstance(ex, dict):
            continue
        exp = ex.get("expires")
        if exp and exp < now:
            continue
        out.append(ex)
    return out

__all__ = [
    "load_policy",
    "get_policy",
    "list_policies",
    "active_exceptions",
    "PolicyError",
]
