from __future__ import annotations
from typing import List, Sequence, Tuple
import math
import random

class TFTMultiHeadStub:
    """Placeholder multi-head temporal model.

    Deterministic (seeded) simple projection producing a pseudo prediction
    and residual vector with interface parity to TFTLite.
    """
    def __init__(self, window: int, feature_dim: int, heads: int = 4, seed: int = 42):
        self.window = window
        self.feature_dim = feature_dim
        self.heads = heads
        self.rnd = random.Random(seed)
        # Pre-generate head weights
        self._weights = [[self.rnd.uniform(-0.05, 0.05) for _ in range(feature_dim)] for _ in range(heads)]

    def forward(self, window_view: Sequence[Sequence[float]]) -> Tuple[List[float], List[float]]:
        if not window_view:
            return [], []
        latest = window_view[-1]
        # Simple multi-head blend of latest vector
        pred = []
        for j in range(self.feature_dim):
            acc = 0.0
            for h in range(self.heads):
                w = self._weights[h][j]
                acc += w * latest[j]
            pred.append(latest[j] + acc)
        residual = [latest[j] - pred[j] for j in range(self.feature_dim)]
        return pred, residual

__all__ = ["TFTMultiHeadStub"]
