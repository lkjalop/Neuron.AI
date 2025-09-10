"""Diminishing Returns & Repository Rotation Services.

Responsibilities:
- Monitor SNN unique ratio (FUSION_SNN_UNIQUE_RATIO_ROLLING) and Hopfield recall contributions.
- If derivative of rolling SNN unique ratio below threshold for sustained windows, disable Hopfield (set hopfield.enabled = false).
- Manage repository neuron rotation (placeholder) to attempt coverage uplift; measure uplift delta.
- Publish governance recommendations (append to executive_agg.guard_trips or future pipeline log) best-effort.

Runtime Params:
  governance.hopfield.plateau.delta_threshold (float) default 0.002
  governance.hopfield.plateau.window_min (int) default 20
  governance.hopfield.plateau.cooldown_s (int) default 900
  repository.rotation.interval_s (int) default 1800
  repository.rotation.enabled (bool)
  repository.rotation.min_delta (float) default 0.01

NOTE: This is a scaffold; real implementation would integrate with reservoir internals.
"""
from __future__ import annotations
import time, threading, json, os
from collections import deque
from config import runtime_params
from core import metrics
from core.main import executive_agg  # reuse governance composite / state

class DiminishingReturnsMonitor:
    def __init__(self):
        self._snn_unique_hist = deque(maxlen=400)
        self._last_plateau_action: float = 0.0
        self._lock = threading.Lock()

    def sample(self):
        # Extract latest SNN unique rolling ratio
        val = 0.0
        try:
            g = metrics.FUSION_SNN_UNIQUE_RATIO_ROLLING  # type: ignore[attr-defined]
            for _k, child in getattr(g, '_metrics', {}).items():  # type: ignore[attr-defined]
                val = float(child._value.get())  # type: ignore[attr-defined]
        except Exception:
            val = 0.0
        with self._lock:
            self._snn_unique_hist.append((time.time(), val))
            self._maybe_plateau(val)

    def _maybe_plateau(self, current: float):
        try:
            if runtime_params:
                thr = float(runtime_params.get_param("governance.hopfield.plateau.delta_threshold") or 0.002)
                win = int(runtime_params.get_param("governance.hopfield.plateau.window_min") or 20)
                cooldown = float(runtime_params.get_param("governance.hopfield.plateau.cooldown_s") or 900)
            else:
                thr, win, cooldown = 0.002, 20, 900
        except Exception:
            thr, win, cooldown = 0.002, 20, 900
        if len(self._snn_unique_hist) < win:
            return
        # Compute derivative over window (first vs last)
        first = self._snn_unique_hist[0][1]
        last = self._snn_unique_hist[-1][1]
        delta = abs(last - first)
        now = time.time()
        if delta < thr and (now - self._last_plateau_action) > cooldown:
            # Disable hopfield
            try:
                runtime_params.update_param("hopfield.enabled", False, reason="plateau_detected", actor="governance")  # type: ignore[attr-defined]
            except Exception:
                pass
            self._last_plateau_action = now
            try:
                executive_agg.record_guard_trip("hopfield_plateau")
            except Exception:
                pass

class RepositoryRotator:
    def __init__(self):
        self._last_rotation: float = 0.0
        self._last_unique_before: float | None = None

    def maybe_rotate(self):
        try:
            if runtime_params:
                enabled = runtime_params.get_param("repository.rotation.enabled")
                if enabled in {0, False, "0", "false"}:
                    return
                interval = float(runtime_params.get_param("repository.rotation.interval_s") or 1800)
            else:
                interval = 1800
        except Exception:
            interval = 1800
        now = time.time()
        if (now - self._last_rotation) < interval:
            return
        # Get pre-rotation unique ratio
        pre = 0.0
        try:
            g = metrics.FUSION_SNN_UNIQUE_RATIO_ROLLING
            for _k, child in getattr(g, '_metrics', {}).items():
                pre = float(child._value.get())
        except Exception:
            pre = 0.0
        # Real rotation hook (scaffold) via core.snn.repository.rotate
        outcome = "success"
        rotation_summary = {}
        try:
            from core.snn import repository  # type: ignore
            rotation_summary = repository.rotate()
        except Exception:
            outcome = "error"
        self._last_rotation = now
        metrics.REPOSITORY_ROTATIONS_TOTAL.labels(outcome=outcome).inc()
    # Post value
        post = 0.0
        try:
            g = metrics.FUSION_SNN_UNIQUE_RATIO_ROLLING
            for _k, child in getattr(g, '_metrics', {}).items():
                post = float(child._value.get())
        except Exception:
            post = pre
        uplift = max(0.0, post - pre)
        # Only emit uplift gauge if rotation succeeded
        if outcome == "success":
            metrics.REPOSITORY_NEURON_COVERAGE_UPLIFT.labels(tenant="global").set(uplift)
            # Basic audit append (best-effort)
            try:
                audit_path = os.path.join("audit", "REPOSITORY_ROTATIONS.jsonl")
                os.makedirs(os.path.dirname(audit_path), exist_ok=True)
                rec = {
                    "ts": now,
                    "pre_unique_ratio": pre,
                    "post_unique_ratio": post,
                    "uplift": uplift,
                    "summary": rotation_summary,
                }
                with open(audit_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec)+"\n")
            except Exception:
                pass

    def _simulate_rotation(self):  # deprecated placeholder retained for backward compat
        return {}

_monitor = DiminishingReturnsMonitor()
_rotator = RepositoryRotator()

class DiminishingService(threading.Thread):
    def __init__(self):
        super().__init__(name="diminishing-service", daemon=True)
        self._stop = threading.Event()

    def run(self):  # pragma: no cover
        while not self._stop.is_set():
            try:
                _monitor.sample()
                _rotator.maybe_rotate()
            except Exception:
                pass
            self._stop.wait(30.0)

    def stop(self):  # pragma: no cover
        self._stop.set()

_service: DiminishingService | None = None

def start():  # pragma: no cover
    global _service
    if _service and _service.is_alive():
        return False
    _service = DiminishingService()
    _service.start()
    return True

__all__ = ["start"]
