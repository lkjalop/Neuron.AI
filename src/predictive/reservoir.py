"""Reservoir SNN scaffold.

Purpose:
  - Provide lightweight, optional reservoir (echo state / liquid state inspired) structure to embed temporal feature vectors.
  - Downstream: emergence probability model, drift characterization, anomaly fusion.

Design Goals:
  - Deterministic initialization (seed input) for reproducibility.
  - Sparse recurrent weight matrix with controlled spectral radius.
  - Simple leaky integration update (no heavy torch autograd dependency for now).
  - Pluggable backend: starts in pure Python/numpy; can switch to torch when available.

Runtime Params (suggested future keys):
  - reservoir.size (int)
  - reservoir.sparsity (0..1)
  - reservoir.spectral_radius (float)
  - reservoir.leak (0..1)

API:
  init_reservoir(size: int, sparsity: float, spectral_radius: float, leak: float, seed: int | None) -> Reservoir
  reservoir.step(input_vec: Sequence[float]) -> state_vector (list[float])
  reservoir.embed(window: list[Sequence[float]]) -> pooled embedding (mean state)

Note: For now we avoid torch dependency usage so this runs even if torch optional install is missing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Optional, List
import math
import random

try:  # optional numpy, fallback to pure python lists if absent
    import numpy as np  # type: ignore
except Exception:  # noqa: BLE001
    np = None  # type: ignore

@dataclass
class ReservoirConfig:
    size: int = 128
    sparsity: float = 0.9  # fraction of zeros
    spectral_radius: float = 0.9
    leak: float = 0.2
    seed: Optional[int] = None

class Reservoir:
    def __init__(self, cfg: ReservoirConfig):
        self.cfg = cfg
        if cfg.seed is not None:
            random.seed(cfg.seed)
        self._init_weights()
        self.state = [0.0] * cfg.size

    def _init_weights(self):
        n = self.cfg.size
        sparsity = self.cfg.sparsity
        # Build sparse matrix in list-of-dicts form for efficiency
        W: List[dict[int, float]] = []
        for i in range(n):
            row = {}
            for j in range(n):
                if random.random() < sparsity:
                    continue
                # small random weight
                row[j] = random.uniform(-1.0, 1.0)
            W.append(row)
        # Approximate spectral radius normalization (heuristic): scale by max abs row-sum
        max_row_sum = max((sum(abs(v) for v in r.values()) for r in W), default=1.0)
        if max_row_sum == 0:
            max_row_sum = 1.0
        scale = (self.cfg.spectral_radius / max_row_sum)
        for r in W:
            for k in r:
                r[k] *= scale
        self.W = W

    def step(self, input_vec: Sequence[float]):
        # Pad / truncate input to state size
        n = self.cfg.size
        if len(input_vec) < n:
            vec = list(input_vec) + [0.0] * (n - len(input_vec))
        else:
            vec = list(input_vec[:n])
        new_state = [0.0] * n
        for i, row in enumerate(self.W):
            acc = 0.0
            for j, w in row.items():
                acc += self.state[j] * w
            acc += vec[i]
            # tanh activation
            val = math.tanh(acc)
            # leaky integration
            new_state[i] = (1 - self.cfg.leak) * self.state[i] + self.cfg.leak * val
        self.state = new_state
        return list(self.state)

    def embed(self, window: Sequence[Sequence[float]]):
        # Reset state for deterministic embedding of a window
        self.state = [0.0] * self.cfg.size
        states: List[List[float]] = []
        for vec in window:
            states.append(self.step(vec))
        # mean pool
        pooled = [0.0] * self.cfg.size
        if not states:
            return pooled
        for s in states:
            for i, v in enumerate(s):
                pooled[i] += v
        for i in range(len(pooled)):
            pooled[i] /= len(states)
        return pooled

# Convenience factory

def init_reservoir(**overrides) -> Reservoir:
    cfg = ReservoirConfig(**overrides)
    return Reservoir(cfg)

__all__ = ["ReservoirConfig", "Reservoir", "init_reservoir"]
