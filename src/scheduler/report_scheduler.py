"""Report Scheduler (skeleton).

Periodically invokes `build_report_bundle` when enabled via runtime params.

Runtime Params:
  report.bundle.enable (bool)
  report.bundle.interval_seconds (int)
"""
from __future__ import annotations

import asyncio, logging
from config.runtime_params import get_param  # type: ignore

log = logging.getLogger("report.scheduler")


async def _loop():  # pragma: no cover (timed loop)
    from reports.unified_pipeline import build_report_bundle  # local import
    while True:
        try:
            if bool(int(get_param("report.bundle.enable") or 0)):
                interval = int(get_param("report.bundle.interval_seconds") or 1800)
                try:
                    res = await build_report_bundle(include_html=True)
                    log.info("report_bundle_generated", extra={"paths": res})
                except Exception:
                    log.exception("report_bundle_generation_failed")
            else:
                interval = 300  # backoff polling when disabled
        except Exception:
            interval = 300
        await asyncio.sleep(max(30, interval))


_TASK: asyncio.Task | None = None


def start(loop: asyncio.AbstractEventLoop):
    global _TASK
    if _TASK and not _TASK.done():
        return False
    _TASK = loop.create_task(_loop())
    return True


__all__ = ["start"]