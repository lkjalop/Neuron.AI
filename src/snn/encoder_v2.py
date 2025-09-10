"""SNN Encoder v2

Transforms Event objects into spike trains with:
 - Stable feature ordering
 - Hash-based seed for deterministic noise injection
 - Simple temporal binning of spikes

Output format: list[list[int]] where outer index = neuron, inner list = spike timestamps (bucket indices)
"""
from __future__ import annotations

from typing import List
import hashlib, math, random

from core.event import Event


def _stable_items(d):
    return sorted((k,v) for k,v in d.items())


def event_seed(event: Event, base_seed: int = 1337) -> int:
    h = hashlib.sha256()
    h.update(str(base_seed).encode())
    h.update(event.event_id.encode())
    if event.tenant_id:
        h.update(event.tenant_id.encode())
    return int(h.hexdigest()[:8], 16)


def encode_event(event: Event, *, neurons: int = 16, buckets: int = 12, base_seed: int = 1337) -> List[List[int]]:
    feats = []
    # severity first for consistency
    if event.severity is not None:
        feats.append(("severity", float(event.severity)))
    # features stable order
    feats.extend([(k, v) for k, v in _stable_items(event.features) if isinstance(v, (int, float))])
    if not feats:
        return [[] for _ in range(neurons)]
    # Normalize values to 0-1 using min/max across present features
    vals = [float(v) for _, v in feats]
    vmin, vmax = min(vals), max(vals)
    rng = (vmax - vmin) or 1.0
    norm = [(k, (float(v)-vmin)/rng) for k,v in feats]

    seed = event_seed(event, base_seed=base_seed)
    rnd = random.Random(seed)

    spikes: List[List[int]] = [[] for _ in range(neurons)]
    for idx, (k, v) in enumerate(norm):
        neuron = idx % neurons
        # Fire proportional number of spikes (1..buckets) by value magnitude
        count = max(1, int(round(v * buckets)))
        for _ in range(count):
            # jitter bucket by small noise for dispersion
            bucket = min(buckets-1, max(0, int(round(v * (buckets-1) + rnd.uniform(-0.25,0.25)))))
            spikes[neuron].append(bucket)
    return spikes

__all__ = ["encode_event", "event_seed"]
