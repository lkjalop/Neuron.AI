"""Deterministic lightweight embedding service (placeholder).

Replaces heavy model inference with a reproducible hash -> vector mapping so that
semantic plumbing can be tested prior to integrating a real model.
"""
from __future__ import annotations

from typing import List
import hashlib, struct


def text_to_vector(text: str, dims: int = 64) -> List[float]:
    # Hash chunks of the text to fill dimension slots
    if not text:
        text = ""
    h = hashlib.sha256(text.encode()).digest()
    # Repeat hash to fill required dims
    needed = dims * 4  # 4 bytes per float
    buf = (h * ((needed // len(h)) + 1))[:needed]
    floats: List[float] = []
    for i in range(0, needed, 4):
        (val,) = struct.unpack("!I", buf[i:i+4])
        floats.append((val % 10000) / 10000.0)
    return floats

__all__ = ["text_to_vector"]
