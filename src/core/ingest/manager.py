from __future__ import annotations

import asyncio
import contextlib
from typing import Optional, Sequence
from core.ratelimit import TokenBucket

from core.event import Event, validate_event
from core import metrics
from .simulated import SimulatedEventSource


class IngestionManager:
    def __init__(self, tenants: Sequence[str], queue_max: int = 10000, *, rate_capacity: int = 1000, rate_fill: float = 500.0):
        self.source = SimulatedEventSource(tenants)
        self.queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=queue_max)
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self.bucket = TokenBucket(capacity=rate_capacity, fill_rate=rate_fill)
        self.tenants = set(tenants)

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(Exception):  # type: ignore
                await self._task

    async def _run(self):
        async for raw in self.source.stream():
            try:
                tenant_id = raw["tenant_id"]
                if tenant_id not in self.tenants:
                    metrics.INGEST_ERRORS_TOTAL.labels(error_type="invalid_tenant").inc()
                    continue
                if not self.bucket.consume():
                    metrics.EVENTS_DROPPED_TOTAL.labels(tenant=tenant_id, reason="rate_limit").inc()
                    continue
                try:
                    ev = Event(
                        tenant_id=tenant_id,
                        source=raw.get("source", "sim"),
                        raw=raw.get("raw", {}),
                        features=raw.get("features", {}),
                        labels=raw.get("labels", {}),
                        meta=raw.get("meta", {}),
                    )
                    validate_event(ev)
                    metrics.EVENTS_TOTAL.labels(tenant=ev.tenant_id).inc()
                except Exception:
                    metrics.INGEST_ERRORS_TOTAL.labels(error_type="validation").inc()
                    continue
                try:
                    self.queue.put_nowait(ev)
                except asyncio.QueueFull:
                    metrics.EVENTS_DROPPED_TOTAL.labels(tenant=tenant_id, reason="queue_full").inc()
            except Exception:
                metrics.INGEST_ERRORS_TOTAL.labels(error_type="unknown").inc()
                continue

    async def get(self) -> Event:
        return await self.queue.get()


__all__ = ["IngestionManager"]
