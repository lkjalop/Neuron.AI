"""Sequence buffering utilities (legacy + temporal scaffold).

This module previously had two separate experimental implementations merged
accidentally causing a SyntaxError (duplicate future import mid-file) and
shadowing of symbols. We now unify them while preserving backward compatibility
for existing imports: ``GLOBAL_SEQUENCE_BUFFER`` and ``SequenceBuffer`` used by
the SNN detector remain stable, while a new vector-oriented normalized window
API is exposed via ``VectorSequenceBuffer`` and ``buffers()``.

Exports:
  - SequenceBuffer (scalar per-tenant rolling series; legacy)
  - GLOBAL_SEQUENCE_BUFFER (singleton instance length=60)
  - VectorSequenceBuffer (per-tenant normalized feature window)
  - BufferManager / buffers() (manager for VectorSequenceBuffer instances)
"""
from __future__ import annotations

from collections import deque
from typing import Deque, Dict, List, Tuple


# ---- Legacy scalar buffer (used by SNN residual forecaster) ----
class SequenceBuffer:
    """Per-tenant fixed-length buffer of recent scalar feature values.

    Provides simple append and tail access. Retained for SNN detector which
    expects ``GLOBAL_SEQUENCE_BUFFER`` with ``add(tenant, value)`` and
    ``tail(tenant)`` methods.
    """

    def __init__(self, length: int = 50):
        self.length = int(length)
        self._data: Dict[str, Deque[float]] = {}

    def add(self, tenant: str, value: float):  # noqa: D401 (simple method)
        d = self._data.setdefault(tenant, deque(maxlen=self.length))
        d.append(float(value))

    def tail(self, tenant: str) -> List[float]:  # noqa: D401
        return list(self._data.get(tenant, []))


GLOBAL_SEQUENCE_BUFFER = SequenceBuffer(length=60)


# ---- Vector normalized buffer (new temporal scaffold) ----
class VectorSequenceBuffer:
    """Fixed-length rolling window of normalized feature vectors.

    Normalization: running per-dimension min/max -> maps values into [0,1].
    Degenerate (hi==lo) dimensions map to 0.0 until variance appears.
    Deterministic and stateful only within each buffer instance.
    """

    def __init__(self, window: int, feature_order: List[str]):
        self.window = int(window)
        self.feature_order = list(feature_order)
        self._buf: Deque[Tuple[float, ...]] = deque(maxlen=self.window)
        self._min = [float("inf")] * len(self.feature_order)
        self._max = [float("-inf")] * len(self.feature_order)

    def add_vector(self, vec: List[float]):
        # Update running min/max
        for i, v in enumerate(vec):
            if v < self._min[i]:
                self._min[i] = v
            if v > self._max[i]:
                self._max[i] = v
        norm: List[float] = []
        for i, v in enumerate(vec):
            lo, hi = self._min[i], self._max[i]
            if hi > lo:
                norm.append((v - lo) / (hi - lo))
            else:
                norm.append(0.0)
        self._buf.append(tuple(norm))

    def window_view(self) -> List[Tuple[float, ...]]:
        return list(self._buf)

    def ready(self) -> bool:
        return len(self._buf) == self.window


class BufferManager:
    """Manages per-tenant VectorSequenceBuffer instances keyed by tenant id."""

    def __init__(self, window: int, feature_order: List[str]):
        self.window = int(window)
        self.feature_order = list(feature_order)
        self._tenants: Dict[str, VectorSequenceBuffer] = {}

    def get(self, tenant: str) -> VectorSequenceBuffer:
        buf = self._tenants.get(tenant)
        if buf is None:
            buf = VectorSequenceBuffer(self.window, self.feature_order)
            self._tenants[tenant] = buf
        return buf


_MANAGER: BufferManager | None = None


def buffers(window: int, feature_order: List[str]) -> BufferManager:
    """Return singleton BufferManager, reinitializing if shape changes."""
    global _MANAGER
    if (
        _MANAGER is None
        or _MANAGER.window != int(window)
        or _MANAGER.feature_order != list(feature_order)
    ):
        _MANAGER = BufferManager(window, feature_order)
    return _MANAGER


__all__ = [
    "SequenceBuffer",
    "GLOBAL_SEQUENCE_BUFFER",
    "VectorSequenceBuffer",
    "BufferManager",
    "buffers",
]
