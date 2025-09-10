"""Periodic resource usage sampler updating Prometheus gauges.

Lightweight thread (not async) to avoid event loop coupling. Sampling interval
is modest (default 5s) to reduce overhead. Safe if psutil not installed: it will
log a warning once and disable itself.
"""
from __future__ import annotations

import os, time, threading, logging
from typing import Optional
from core import metrics

log = logging.getLogger("neuron.resource_monitor")

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore


class ResourceMonitor:
    def __init__(self, interval: float = 5.0):
        self.interval = interval
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._started = False

    def start(self):
        if self._started:
            return
        if psutil is None:
            log.warning("psutil not installed; resource monitoring disabled")
            return
        self._started = True
        self._thread = threading.Thread(target=self._run, name="resource-monitor", daemon=True)
        self._thread.start()
        log.info("Resource monitor thread started (interval=%ss)", self.interval)

    def stop(self):
        if not self._started:
            return
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self._started = False

    def _run(self):
        proc = psutil.Process(os.getpid())  # type: ignore[attr-defined]
        while not self._stop.is_set():
            try:
                mem_mb = proc.memory_info().rss / (1024 * 1024)
                cpu_pct = proc.cpu_percent(interval=None)  # non-blocking sample
                metrics.SYSTEM_MEMORY_MB.set(mem_mb)  # type: ignore[attr-defined]
                metrics.SYSTEM_CPU_PERCENT.set(cpu_pct)  # type: ignore[attr-defined]
            except Exception as e:  # noqa: BLE001
                log.debug("Resource sampling error: %s", e)
            self._stop.wait(self.interval)


monitor = ResourceMonitor()

__all__ = ["monitor", "ResourceMonitor"]
