"""Synthetic Event Generator Adapter

Provides configurable synthetic event streams for testing detectors.
Supports anomaly injection via periodic spikes or custom callback.
"""
from __future__ import annotations

from typing import Iterator, Callable, Optional
import math, random, time

from core.event import Event


class SyntheticProfile:
    def __init__(self, base_severity: float = 1.0, noise: float = 0.3, spike_severity: float = 8.0):
        self.base = base_severity
        self.noise = noise
        self.spike = spike_severity

    def value(self, i: int) -> float:
        # mild seasonal variation + noise
        seasonal = math.sin(i / 30.0) * 0.5
        return max(0.0, self.base + seasonal + random.random() * self.noise)


def synthetic_stream(
    *,
    count: int = 500,
    tenant_id: str | None = None,
    anomaly_period: int = 111,
    profile: Optional[SyntheticProfile] = None,
    anomaly_injector: Optional[Callable[[int, Event], None]] = None,
    sleep: float | None = None,
) -> Iterator[Event]:
    profile = profile or SyntheticProfile()
    for i in range(count):
        sev = profile.value(i)
        is_anomaly = anomaly_period > 0 and (i % anomaly_period == 0 and i > 0)
        if is_anomaly:
            sev = profile.spike
        evt = Event.create(
            "synthetic",
            tenant_id=tenant_id,
            severity=sev,
            features={"i": i, "is_anom": is_anomaly},
            source="synthetic",
        )
        if anomaly_injector:
            try:
                anomaly_injector(i, evt)
            except Exception:
                pass
        yield evt
        if sleep:
            time.sleep(sleep)

__all__ = ["synthetic_stream", "SyntheticProfile"]
