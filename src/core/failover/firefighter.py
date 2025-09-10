"""Firefighter (Automated Triage) Stub - Phase 3

Purpose: Minimal incident aggregation around SNN resource guard disable cycles.

Functionality (stub):
- Track timestamps of SNN disable events (resource guard triggers).
- Produce incident dict if cycles exceed threshold within window.
- Suppress duplicate incidents for a cooldown interval.

Future (Phase 4+): root cause classification, recommendation engine, integration with fusion arbitration.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class DisableCycleWindow:
    window_sec: float = 600.0  # 10 minutes
    threshold: int = 3         # triggers incident if >= threshold disable events in window
    suppress_cooldown_sec: float = 120.0
    _events: List[float] = field(default_factory=list)
    _last_incident_ts: float | None = None

    def add_disable(self, ts: float | None = None) -> None:
        ts = ts or time.time()
        self._events.append(ts)
        # prune
        cutoff = ts - self.window_sec
        self._events = [t for t in self._events if t >= cutoff]

    def evaluate(self) -> Dict[str, Any] | None:
        now = time.time()
        # prune old
        cutoff = now - self.window_sec
        self._events = [t for t in self._events if t >= cutoff]
        if len(self._events) >= self.threshold:
            if self._last_incident_ts and (now - self._last_incident_ts) < self.suppress_cooldown_sec:
                return None
            self._last_incident_ts = now
            return {
                "type": "snn_disable_cycle",
                "cycles": len(self._events),
                "window_sec": self.window_sec,
                "threshold": self.threshold,
                "first_cycle_ts": min(self._events),
                "last_cycle_ts": max(self._events),
                "generated_ts": now,
            }
        return None

__all__ = ["DisableCycleWindow"]


def derive_recommendations(incidents: list[dict]) -> list[dict]:
    """Generate simple recommendations from incidents list.

    Heuristics:
      - If >=2 disable cycle incidents in last 10 minutes: suggest cooldown increase.
      - If max cycles >= threshold*2: suggest root cause classification (latency vs density) & temporary SAFE_MODE consideration.
    """
    recs = []
    now = time.time()
    disable = [i for i in incidents if i.get("type") == "snn_disable_cycle"]
    recent = [i for i in disable if (now - i.get("generated_ts", now)) < 600]
    if len(recent) >= 2:
        recs.append({
            "action": "increase_cooldown",
            "priority": "medium",
            "reason": f"{len(recent)} disable cycles in last 10m",
            "suggested_param_patch": {"snn.guard.cooldown_s": "+50%"},
        })
    if disable:
        max_cycles = max(i.get("cycles", 0) for i in disable)
        thr = disable[-1].get("threshold", 3)
        if max_cycles >= thr * 2:
            recs.append({
                "action": "root_cause_analysis",
                "priority": "high",
                "reason": f"max cycles {max_cycles} >= 2x threshold {thr}",
                "next_steps": ["inspect latency p95", "inspect spike density trend", "consider SAFE_MODE if persistent"],
            })
    if not recs:
        recs.append({"action": "observe", "priority": "low", "reason": "no material issues detected"})
    return recs

__all__.append("derive_recommendations")
