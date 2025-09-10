"""Version applicability parsing & evaluation utilities.

Provides minimal CPE 2.3 URI parsing and semver-ish comparison helpers
sufficient for gating component->vulnerability matches.

Scope (foundation):
 - Parse CPE 2.3 URIs of form: cpe:2.3:part:vendor:product:version:update:edition:lang:swEdition:targetSw:targetHw:other
 - Extract vendor, product, version, part.
 - Evaluate NVD configuration nodes' cpeMatch entries containing versionStartIncluding,
   versionStartExcluding, versionEndIncluding, versionEndExcluding keys against a component version.
 - Semver comparison supporting major.minor.patch (numeric) else lexical fallback.

Assumptions / Simplifications:
 - Wildcard version component in CPE ("*") matches any version.
 - We do not yet expand logical nodes (AND/OR) beyond treating each cpeMatch independently; future
   enhancement could implement full boolean logic. Current usage is coarse filtering: if ANY cpeMatch
   indicates applicability we accept.
 - Component version normalization trims common prefix 'v'.
 - Pre-release/build metadata ignored.

License: Internal utility (no external dependencies beyond stdlib).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Iterable, Dict, Any
import re

CPE23_PREFIX = "cpe:2.3:"

@dataclass
class CPE23:
    part: str
    vendor: str
    product: str
    version: str | None

_cpe_split_re = re.compile(r":")


def parse_cpe23(uri: str) -> Optional[CPE23]:
    if not uri or not uri.startswith(CPE23_PREFIX):
        return None
    parts = _cpe_split_re.split(uri)
    # Expect at least 6 tokens: cpe,2.3,part,vendor,product,version
    if len(parts) < 6:
        return None
    try:
        part = parts[2]
        vendor = parts[3]
        product = parts[4]
        version = parts[5]
    except Exception:
        return None
    if version in ("*", "-"):
        version = None
    return CPE23(part=part, vendor=vendor, product=product, version=version)

_semver_token_re = re.compile(r"[^0-9]+")


def _normalize_version(v: str | None) -> Optional[str]:
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    if v.startswith("v") and len(v) > 1 and v[1].isdigit():
        v = v[1:]
    return v


def _split_semver(v: str) -> list[str]:
    tokens = v.split(".")
    return tokens


def compare_semver(a: str, b: str) -> int:
    """Compare two version strings with semver-ish logic.

    Returns <0 if a < b, 0 if equal, >0 if a > b.
    - Numeric tokens compared numerically; non-numeric cause lexical fallback for that token.
    - Length mismatch: missing tokens treated as 0 if numeric; otherwise lexical fallback.
    """
    if a == b:
        return 0
    a_n = _normalize_version(a) or ""
    b_n = _normalize_version(b) or ""
    a_parts = _split_semver(a_n)
    b_parts = _split_semver(b_n)
    max_len = max(len(a_parts), len(b_parts))
    for i in range(max_len):
        at = a_parts[i] if i < len(a_parts) else "0"
        bt = b_parts[i] if i < len(b_parts) else "0"
        if at.isdigit() and bt.isdigit():
            ai = int(at)
            bi = int(bt)
            if ai != bi:
                return -1 if ai < bi else 1
            continue
        # Lexical fallback
        if at != bt:
            return -1 if at < bt else 1
    return 0


def version_in_range(component_version: str | None, start_incl: str | None = None, start_excl: str | None = None,
                      end_incl: str | None = None, end_excl: str | None = None) -> bool:
    """Determine if component_version satisfies provided range constraints.

    Precedence: inclusive & exclusive respected; if both start_incl and start_excl provided,
    start_incl takes precedence (same for end). Missing component_version returns False.
    """
    component_version = _normalize_version(component_version)
    if component_version is None:
        return False
    # Start bound
    if start_incl:
        if compare_semver(component_version, start_incl) < 0:
            return False
    elif start_excl:
        if compare_semver(component_version, start_excl) <= 0:
            return False
    # End bound
    if end_incl:
        if compare_semver(component_version, end_incl) > 0:
            return False
    elif end_excl:
        if compare_semver(component_version, end_excl) >= 0:
            return False
    return True


def any_cpe_match_applies(cpe_matches: Iterable[Dict[str, Any]], component_version: str | None) -> bool:
    """Return True if any supplied cpeMatch dict applies to the component version.

    A cpeMatch applies if its version range (if any) includes the component version.
    If a cpeMatch has no range qualifiers (and is marked vulnerable==True), it applies.
    """
    for cm in cpe_matches:
        if not isinstance(cm, dict):
            continue
        if not cm.get("vulnerable", True):
            continue
        start_incl = cm.get("versionStartIncluding")
        start_excl = cm.get("versionStartExcluding")
        end_incl = cm.get("versionEndIncluding")
        end_excl = cm.get("versionEndExcluding")
        if not any([start_incl, start_excl, end_incl, end_excl]):
            # No version gating => applies universally
            return True
        try:
            if version_in_range(component_version, start_incl, start_excl, end_incl, end_excl):
                return True
        except Exception:
            continue
    return False

__all__ = [
    "CPE23",
    "parse_cpe23",
    "compare_semver",
    "version_in_range",
    "any_cpe_match_applies",
]
