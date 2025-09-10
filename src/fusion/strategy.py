"""Fusion Strategy Interfaces

Defines minimal interface for combining multiple detector outputs into a
single fused anomaly score / decision. Strategies may leverage runtime
parameters (via param_store) and temporal context.
"""
from __future__ import annotations

from typing import List, Protocol

from detect.orchestrator import Anomaly


class FusionStrategy(Protocol):
    name: str
    def fuse(self, anomalies: List[Anomaly]) -> List[Anomaly]:  # may modify or add fused anomaly
        ...

__all__ = ["FusionStrategy"]
