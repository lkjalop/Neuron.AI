from __future__ import annotations
import math
from typing import Dict, Any, Iterable

"""Neuromorphic signal adapter.
Phase 1: heuristic placeholder using existing SNN activity metrics if available, else derive a simple stability ratio.
"""

def compute_neuromorphic_signal(events: Iterable[Dict[str, Any]], params: Dict[str, Any]) -> float:
    # Placeholder: attempt to read precomputed spike metrics in events; else use variance heuristic.
    spikes = []
    values = []
    for ev in events:
        if "spike_density" in ev:
            spikes.append(ev["spike_density"])
        v = ev.get("value")
        if isinstance(v, (int, float)):
            values.append(float(v))
    neu_mode = params.get("scanner.neuromorphic.mode", "variance")
    if neu_mode == "spike_density" and spikes:
        avg = sum(spikes) / max(1, len(spikes))
        return round(min(1.0, max(0.0, avg)), 6)
    # variance-based heuristic - more variance => higher potential exploit signal (placeholder logic)
    if len(values) > 3:
        mean = sum(values) / len(values)
        var = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        norm = 1 - math.exp(-var / (params.get("scanner.neuromorphic.var_scale", 100.0)))
        return round(min(1.0, max(0.0, norm)), 6)
    return 0.0
