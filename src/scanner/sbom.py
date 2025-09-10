from __future__ import annotations
from typing import Dict, Any, Iterable, List
import json
from .models import Component

def parse_spdx(doc: Dict[str, Any]) -> List[Component]:
    """Very small SPDX (JSON) component extractor.

    Supports documents with top-level 'packages' list. We map each package to Component.
    Fields used: name, versionInfo, downloadLocation (as purl fallback), license concluded ignored.
    """
    components: List[Component] = []
    for pkg in doc.get("packages", []):
        name = pkg.get("name")
        version = pkg.get("versionInfo") or pkg.get("version")
        purl = pkg.get("purl") or pkg.get("downloadLocation")
        if not name:
            continue
        hash_id = f"{name}:{version}:{purl}" if purl else f"{name}:{version}"
        components.append(Component(
            id=hash_id,
            name=name,
            version=version,
            purl=purl,
            ecosystem=pkg.get("primaryPackagePurpose"),
            raw_json=pkg,
        ))
    return components

# Minimal CycloneDX JSON parser for components

def parse_cyclonedx(doc: Dict[str, Any]) -> List[Component]:
    components = []
    for comp in doc.get("components", []) or []:
        name = comp.get("name") or "unknown"
        version = comp.get("version") or comp.get("versionInfo") or ""
        purl = comp.get("purl")
        hash_id = f"{name}:{version}:{purl}" if purl else f"{name}:{version}"
        components.append(Component(
            id=hash_id,
            name=name,
            version=version,
            purl=purl,
            ecosystem=comp.get("type") or comp.get("group") or "library",
            raw_json=comp,
        ))
    return components

__all__ = ["parse_cyclonedx", "parse_spdx"]
