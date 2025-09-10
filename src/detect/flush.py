"""Flush Helper Module

Provides centralized utilities for detector and pipeline flush operations.
Intended responsibilities:
 - Finalize batch-oriented detectors (e.g., model retrain, buffered anomalies)
 - Persist any transient state snapshots
 - Emit flush metrics / latency

Future extensions: integrate with anomaly sink batching or streaming output.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterable, Protocol

from core import metrics


class Flushable(Protocol):  # pragma: no cover - interface only
    def flush(self) -> None: ...  # noqa: D401


@contextmanager
def flush_timer(detector_name: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        try:
            metrics.DETECTOR_LATENCY.labels(tenant="global", detector=f"{detector_name}_flush").observe(elapsed)
        except Exception:
            pass


def flush_all(detectors: Iterable[Flushable]):
    for det in detectors:
        name = getattr(det, "name", det.__class__.__name__)
        try:
            with flush_timer(name):
                det.flush()
        except Exception:  # swallow to keep shutdown resilient
            continue

__all__ = ["flush_all", "Flushable"]
