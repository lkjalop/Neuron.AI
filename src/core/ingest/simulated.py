from __future__ import annotations

import asyncio
import random
import time
from typing import AsyncIterator, Dict, Any, Sequence

from .base import EventSource

DEFAULT_SOURCES: Sequence[str] = ["proc", "net", "fs"]


class SimulatedEventSource(EventSource):
    def __init__(self, tenants: Sequence[str], interval: float = 0.01):
        self.tenants = tenants
        self.interval = interval

    async def stream(self) -> AsyncIterator[Dict[str, Any]]:
        while True:
            await asyncio.sleep(self.interval)
            tenant = random.choice(self.tenants)
            yield {
                "tenant_id": tenant,
                "timestamp": time.time(),
                "source": random.choice(DEFAULT_SOURCES),
                "raw": {"cpu": random.random(), "io": random.randint(0, 1000)},
                "features": {"cpu": random.random(), "io": random.randint(0, 1000)},
                "labels": {},
                "meta": {},
            }

