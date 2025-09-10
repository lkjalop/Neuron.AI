"""Token bucket rate limiter for ingestion throttling."""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class TokenBucket:
    capacity: int
    fill_rate: float  # tokens per second
    tokens: float | None = None
    timestamp: float | None = None

    def _sync(self):
        now = time.time()
        if self.tokens is None:
            self.tokens = float(self.capacity)
            self.timestamp = now
            return
        assert self.timestamp is not None
        elapsed = now - self.timestamp
        self.timestamp = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)

    def consume(self, n: float = 1.0) -> bool:
        self._sync()
        assert self.tokens is not None
        if self.tokens >= n:
            self.tokens -= n
            return True
        return False

    def available(self) -> float:
        self._sync()
        return float(self.tokens or 0.0)


__all__ = ["TokenBucket"]
