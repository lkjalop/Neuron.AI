"""ATT&CK Coverage Matrix (skeleton).

Tracks mapping of ATT&CK technique IDs to detection sources and controls.
Provides summary stats to quantify coverage density and gaps.
"""
from __future__ import annotations

from typing import Dict, Set, Any

_TECHNIQUES: Dict[str, Dict[str, Set[str]]] = {}


def add_mapping(technique: str, detection: str | None = None, control: str | None = None):
    rec = _TECHNIQUES.setdefault(technique, {"detections": set(), "controls": set()})
    if detection:
        rec["detections"].add(detection)
    if control:
        rec["controls"].add(control)


def coverage_summary() -> Dict[str, Any]:
    total = len(_TECHNIQUES)
    if total == 0:
        return {"total": 0, "avg_detection_count": 0.0, "avg_control_count": 0.0, "techniques": []}
    det_counts = [len(v["detections"]) for v in _TECHNIQUES.values()]
    ctrl_counts = [len(v["controls"]) for v in _TECHNIQUES.values()]
    return {
        "total": total,
        "avg_detection_count": sum(det_counts) / total,
        "avg_control_count": sum(ctrl_counts) / total,
        "techniques": [
            {
                "id": t,
                "detections": sorted(v["detections"]),
                "controls": sorted(v["controls"]),
            } for t, v in _TECHNIQUES.items()
        ],
    }


__all__ = ["add_mapping", "coverage_summary"]
