"""Precision Proxy Simulation Module.

Tracks 'noise windows' (expected no-signal periods) to approximate false positive rates for detectors.

Runtime Params:
  precision.proxy.enabled (bool)
  precision.proxy.window.seconds (int) default 60
  precision.proxy.detectors (csv) optional list of detector names to track, default all seen

Endpoints (added in main):
  POST /precision/proxy/simulate {"tenant": "tenantA", "detector": "baseline", "anomalies": 2, "window": 60}

Metrics updated:
  PRECISION_PROXY_WINDOWS (tenant)
  PRECISION_PROXY_FALSE_POSITIVE (tenant, detector)
  PRECISION_PROXY_RATE (tenant, detector)
"""
from __future__ import annotations
import time
from typing import Dict, Tuple
from config import runtime_params
from core import metrics

class PrecisionProxy:
    def __init__(self):
        self._counts: Dict[Tuple[str,str], int] = {}  # (tenant, detector) -> anomalies_in_noise
        self._windows: Dict[str, int] = {}  # tenant -> windows count
        self._last_rate: Dict[Tuple[str,str], float] = {}

    def enabled(self) -> bool:
        try:
            v = runtime_params.get_param("precision.proxy.enabled")
            if v in {0, False, "0", "false"}:
                return False
        except Exception:
            pass
        return True

    def record_window(self, tenant: str, detector: str, anomalies: int, window_seconds: int):
        if not self.enabled():
            return {"status": "disabled"}
        key = (tenant, detector)
        self._windows[tenant] = self._windows.get(tenant, 0) + 1
        if anomalies > 0:
            self._counts[key] = self._counts.get(key, 0) + anomalies
            metrics.PRECISION_PROXY_FALSE_POSITIVE.labels(tenant=tenant, detector=detector).inc(anomalies)
        metrics.PRECISION_PROXY_WINDOWS.labels(tenant=tenant).inc()
        # Rate = false positives / windows
        windows = self._windows[tenant]
        fp = self._counts.get(key, 0)
        rate = fp / max(1, windows)
        self._last_rate[key] = rate
        metrics.PRECISION_PROXY_RATE.labels(tenant=tenant, detector=detector).set(rate)
        return {"tenant": tenant, "detector": detector, "windows": windows, "false_positive": fp, "rate": rate}

_proxy: PrecisionProxy | None = None

def proxy() -> PrecisionProxy:
    global _proxy
    if _proxy is None:
        _proxy = PrecisionProxy()
    return _proxy

__all__ = ["proxy", "PrecisionProxy"]
