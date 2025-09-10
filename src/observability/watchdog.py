"""Processing Watchdog & Self-Healing.

Monitors anomaly/event backlog (simulated via metric placeholder) and enforces
back-off by temporarily lowering temporal detection weight or raising thresholds
when sustained lag crosses a runtime-configurable threshold.
"""
from __future__ import annotations
import asyncio, time, logging
from typing import Optional
from config import runtime_params  # type: ignore
try:
    from core import metrics  # type: ignore
except Exception:  # pragma: no cover
    class _M:  # minimal stub
        INGEST_QUEUE_DEPTH = None
    metrics = _M()  # type: ignore

try:
    from observability.tracing import span  # type: ignore
except Exception:  # pragma: no cover
    from contextlib import contextmanager as _cm
    def span(name: str, **tags):  # type: ignore
        @_cm
        def _s():
            yield
        return _s()

log = logging.getLogger("watchdog")

_TASK: Optional[asyncio.Task] = None


def _read_backlog() -> float:
    g = getattr(metrics, 'INGEST_QUEUE_DEPTH', None)
    if g is None:
        return 0.0
    try:
        # gauge has labels; sum across if necessary
        if hasattr(g, '_metrics'):
            total = 0.0
            for _k, child in g._metrics.items():  # type: ignore[attr-defined]
                try:
                    total += float(child._value.get())  # type: ignore[attr-defined]
                except Exception:
                    continue
            return total
        return float(g._value.get())  # type: ignore[attr-defined]
    except Exception:
        return 0.0


async def _loop():  # pragma: no cover
    cooldown_s = 600
    last_action = 0.0
    while True:
        try:
            if not bool(int(runtime_params.get_param("watchdog.enable") or 0)):
                await asyncio.sleep(60)
                continue
            threshold = float(runtime_params.get_param("watchdog.backlog.threshold") or 500)
            weight_param = "detection.temporal.weight"
            backoff_factor = float(runtime_params.get_param("watchdog.backoff.factor") or 0.5)
            restore_after = int(runtime_params.get_param("watchdog.restore.after_s") or 900)
            backlog = _read_backlog()
            now = time.time()
            with span("watchdog.cycle", backlog=backlog):
                cur_w = runtime_params.get_param(weight_param)
                try:
                    cur_wf = float(cur_w or 0.0)
                except Exception:
                    cur_wf = 0.0
                if backlog >= threshold and (now - last_action) > cooldown_s:
                    # apply backoff
                    new_w = max(0.01, cur_wf * backoff_factor)
                    runtime_params.set_param(weight_param, new_w, actor="watchdog")  # type: ignore[attr-defined]
                    last_action = now
                    log.warning("watchdog_backoff", extra={"backlog": backlog, "weight_old": cur_wf, "weight_new": new_w})
                elif backlog < threshold * 0.3 and (now - last_action) > restore_after and cur_wf < 0.09:
                    # restore gradually
                    new_w = min(0.1, cur_wf * 1.5)
                    runtime_params.set_param(weight_param, new_w, actor="watchdog")  # type: ignore[attr-defined]
                    last_action = now
                    log.info("watchdog_restore", extra={"backlog": backlog, "weight_old": cur_wf, "weight_new": new_w})
            await asyncio.sleep(int(runtime_params.get_param("watchdog.interval_s") or 120))
        except Exception:
            await asyncio.sleep(180)


def start(loop: asyncio.AbstractEventLoop):
    global _TASK
    if _TASK and not _TASK.done():
        return False
    _TASK = loop.create_task(_loop())
    return True

__all__ = ["start"]
