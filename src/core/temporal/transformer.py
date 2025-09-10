"""Temporal Transformer Scaffold.

Provides a rolling window manager and a placeholder attention-based deviation score.
Flag gated by `detection.temporal.enable_transformer`.
"""
from __future__ import annotations
from collections import deque
from typing import Deque, List
import math
from config import runtime_params

class WindowBuffer:
    def __init__(self, size: int):
        self.size = size
        self._buf: Deque[List[float]] = deque(maxlen=size)
    def add(self, vec: List[float]):
        self._buf.append(vec)
    def ready(self) -> bool:
        return len(self._buf) == self.size
    def matrix(self) -> List[List[float]]:
        return list(self._buf)

class SimpleAttentionEncoder:
    def __init__(self):
        pass
    def score(self, mat: List[List[float]]) -> float:
        if not mat:
            return 0.0
        # Placeholder: compute per-position variance mean as pseudo-attention energy
        # Future: real multi-head attention
        cols = len(mat[0])
        var_sum = 0.0
        for j in range(cols):
            col = [row[j] for row in mat]
            mu = sum(col)/len(col)
            var = sum((x-mu)**2 for x in col)/len(col)
            var_sum += var
        return math.tanh(var_sum / (cols or 1))

class TemporalTransformerScaffold:
    def __init__(self, window: int = 16):
        self.window = window
        self.buffer = WindowBuffer(window)
        self.encoder = SimpleAttentionEncoder()
    def ingest(self, vec: List[float]):
        self.buffer.add(vec)
    def deviation(self) -> float:
        if not self.buffer.ready():
            return 0.0
        return self.encoder.score(self.buffer.matrix())

_tt_instance: TemporalTransformerScaffold | None = None

def instance() -> TemporalTransformerScaffold:
    global _tt_instance
    if _tt_instance is None:
        _tt_instance = TemporalTransformerScaffold()
    return _tt_instance

__all__ = ["TemporalTransformerScaffold", "instance"]
