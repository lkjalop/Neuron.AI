"""Secrets manager stub.

Future integration points: Vault / KMS / HSM.
Current behavior: reads from environment variables with simple TTL cache.
"""
from __future__ import annotations

import os, time, threading
from typing import Any


class SecretManager:
    def __init__(self, ttl: int = 300):
        self.ttl = ttl
        self._cache: dict[str, tuple[Any, float]] = {}
        self._lock = threading.Lock()

    def get(self, name: str, default: Any | None = None) -> Any:
        now = time.time()
        with self._lock:
            if name in self._cache:
                val, exp = self._cache[name]
                if now < exp:
                    return val
            val = os.getenv(name, default)
            self._cache[name] = (val, now + self.ttl)
            return val

    def rotate(self, name: str) -> dict[str, Any]:
        # Placeholder: Real rotation might emit an event / integrate with workflow.
        return {"status": "scheduled", "name": name, "ts": time.time()}


secret_manager = SecretManager()

__all__ = ["secret_manager", "SecretManager"]
