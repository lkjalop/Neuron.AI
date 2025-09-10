from __future__ import annotations
"""Alert routing scaffold for vulnerability automation.

Provides:
 - Channel registry (register simple callable sinks)
 - Suppression / cooldown layer (per key: (type,severity,channel))
 - Max burst limiter per channel window (simple token bucket)
 - Metrics wiring: actionable vs suppressed vs dispatch outcome

Runtime parameters consulted (optional, via config.runtime_params if available):
  alert.cooldown.seconds (default 300)
  alert.max_burst (default 5)
  alert.burst_refill_seconds (default 300)
  alert.enabled (default true)
  alert.suppression.levels (mapping optional)  # future use

Usage:
  router = AlertRouter()
  router.register_channel('slack', slack_send_fn)
  router.emit({'type': 'sla_breach', 'severity': 'CRITICAL', 'text': 'Critical SLA breach 5 findings'})

Note: This is a lightweight placeholder. Integrations should replace channel stubs with robust clients.
"""
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple

from core.metrics import (
    VULN_ALERT_DISPATCH_TOTAL,
    VULN_ALERT_ACTIONABLE_TOTAL,
    VULN_ALERT_SUPPRESSED_TOTAL,
    VULN_AUTOMATION_EVENTS_TOTAL,
)

try:  # runtime params optional
    from config import runtime_params  # type: ignore
except Exception:  # pragma: no cover
    runtime_params = None  # type: ignore

ChannelFunc = Callable[[dict], None]

@dataclass
class _Bucket:
    capacity: int
    tokens: float
    refill_seconds: float
    last: float

    def allow(self) -> bool:
        now = time.time()
        elapsed = now - self.last
        if elapsed > 0:
            # linear refill
            rate = self.capacity / max(self.refill_seconds, 1.0)
            self.tokens = min(self.capacity, self.tokens + elapsed * rate)
            self.last = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False

@dataclass
class AlertRouter:
    channels: Dict[str, ChannelFunc] = field(default_factory=dict)
    cooldowns: Dict[Tuple[str, str, str], float] = field(default_factory=dict)  # key -> next_allowed_ts
    buckets: Dict[str, _Bucket] = field(default_factory=dict)

    def _param(self, key: str, default):
        try:
            if runtime_params:
                v = runtime_params.get_param(key)
                if v is not None:
                    return v
        except Exception:
            pass
        return default

    def register_channel(self, name: str, func: ChannelFunc):
        self.channels[name] = func
        # Create bucket lazily on first emit

    def _bucket(self, channel: str) -> _Bucket:
        b = self.buckets.get(channel)
        if b:
            return b
        capacity = int(self._param('alert.max_burst', 5))
        refill_s = float(self._param('alert.burst_refill_seconds', 300))
        b = _Bucket(capacity=capacity, tokens=float(capacity), refill_seconds=refill_s, last=time.time())
        self.buckets[channel] = b
        return b

    def _cooldown_seconds(self) -> float:
        return float(self._param('alert.cooldown.seconds', 300.0))

    def _enabled(self) -> bool:
        v = self._param('alert.enabled', 1)
        return v not in {0, '0', False, 'false'}

    def emit(self, payload: dict, channel: str = 'slack') -> bool:
        """Attempt to send an alert.

        payload expected keys: type, severity (optional), text (human message) + extras.
        Returns True if dispatched, False if suppressed.
        """
        if not self._enabled():
            VULN_ALERT_SUPPRESSED_TOTAL.labels(channel=channel, reason='disabled').inc()
            return False
        ch = self.channels.get(channel)
        if not ch:
            VULN_ALERT_DISPATCH_TOTAL.labels(outcome='error').inc()
            return False
        a_type = str(payload.get('type') or 'generic')
        severity = str(payload.get('severity') or 'NA').upper()
        key = (a_type, severity, channel)
        now = time.time()
        # Cooldown suppression
        next_allowed = self.cooldowns.get(key, 0.0)
        if now < next_allowed:
            VULN_ALERT_SUPPRESSED_TOTAL.labels(channel=channel, reason='cooldown').inc()
            VULN_ALERT_DISPATCH_TOTAL.labels(outcome='suppressed').inc()
            return False
        # Burst limiter
        if not self._bucket(channel).allow():
            VULN_ALERT_SUPPRESSED_TOTAL.labels(channel=channel, reason='burst').inc()
            VULN_ALERT_DISPATCH_TOTAL.labels(outcome='suppressed').inc()
            return False
        # Dispatch
        try:
            ch(payload)
            VULN_ALERT_DISPATCH_TOTAL.labels(outcome='success').inc()
            VULN_ALERT_ACTIONABLE_TOTAL.labels(channel=channel).inc()
            VULN_AUTOMATION_EVENTS_TOTAL.labels(type='alert_dispatch').inc()
            # Set cooldown
            self.cooldowns[key] = now + self._cooldown_seconds()
            return True
        except Exception:
            VULN_ALERT_DISPATCH_TOTAL.labels(outcome='error').inc()
            return False

# Simple built-in stub channel

def slack_stub(payload: dict):  # pragma: no cover - placeholder side-effect
    # Real implementation would format and POST to Slack webhook
    # Here we just print/log best-effort
    msg = f"[SLACK-STUB] {payload.get('type')} {payload.get('severity')} :: {payload.get('text')}"
    print(msg)

__all__ = [
    'AlertRouter',
    'slack_stub',
]
