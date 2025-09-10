"""Upstash Redis REST client stub.

Provides a minimal GET/SET abstraction using REST API.
"""
from __future__ import annotations

import os, json, time
from typing import Optional

try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None  # type: ignore


class UpstashRedis:
    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.token = token

    def _client(self):  # lazy httpx client creation per request (stateless)
        if httpx is None:
            raise RuntimeError("httpx not installed for Upstash client")
        return httpx

    def get(self, key: str) -> Optional[str]:
        try:
            r = self._client().get(f"{self.url}/get/{key}", headers={"Authorization": f"Bearer {self.token}"}, timeout=5.0)
            if r.status_code == 200:
                return r.json().get("result")
        except Exception:
            return None
        return None

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        args = [value]
        if ex is not None:
            args.extend(["EX", str(ex)])
        try:
            r = self._client().get(
                f"{self.url}/set/{key}/{'/'.join(args)}",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5.0,
            )
            return r.status_code == 200
        except Exception:
            return False


_INSTANCE: UpstashRedis | None = None


def redis() -> UpstashRedis | None:
    global _INSTANCE
    if _INSTANCE is None:
        url = os.getenv("UPSTASH_REDIS_REST_URL")
        token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
        if url and token:
            _INSTANCE = UpstashRedis(url, token)
    return _INSTANCE


__all__ = ["redis", "UpstashRedis"]
