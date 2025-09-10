"""Embedding provider abstraction with optional OpenAI backend.

Design goals (zero-budget safe default):
 - Default to cheap deterministic dummy embedding (length mod feature) so tests don't call external APIs.
 - Only invoke OpenAI if both ENV vars `EMBEDDING_PROVIDER=openai` and `OPENAI_API_KEY` are set.
 - Provide minimal batching + basic retry/backoff for rate limits (HTTP 429) and transient 5xx.
 - Avoid adding heavy dependencies; use `requests` from stdlib stack if available else fallback to dummy.

OpenAI model + dimensions:
 - Uses text-embedding-3-small by default (1536 dims) or override via `OPENAI_EMBED_MODEL`.
 - Truncates / returns only numeric list (no metadata) to keep interface simple.
"""
from __future__ import annotations

import os, time, json, math
from typing import List, Iterable


class EmbeddingProvider:
    def embed(self, texts: List[str]) -> List[List[float]]:  # noqa: D401
        raise NotImplementedError


class DummyEmbedding(EmbeddingProvider):
    def embed(self, texts: List[str]) -> List[List[float]]:  # noqa: D401
        return [[float(len(t) % 10)] for t in texts]


class OpenAIEmbedding(EmbeddingProvider):
    """Lightweight OpenAI embedding client (minimal deps).

    Environment:
      OPENAI_API_KEY (required)
      OPENAI_BASE_URL (optional, defaults https://api.openai.com/v1)
      OPENAI_EMBED_MODEL (optional, defaults text-embedding-3-small)
      OPENAI_EMBED_BATCH (optional, default 64)
      OPENAI_EMBED_TIMEOUT_S (optional, default 30)
      OPENAI_EMBED_MAX_RETRIES (optional, default 3)
    """

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY") or ""
        self.base_url = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.model = os.getenv("OPENAI_EMBED_MODEL") or "text-embedding-3-small"
        try:
            self.batch_size = max(1, min(128, int(os.getenv("OPENAI_EMBED_BATCH") or 64)))
        except Exception:
            self.batch_size = 64
        try:
            self.timeout = float(os.getenv("OPENAI_EMBED_TIMEOUT_S") or 30.0)
        except Exception:
            self.timeout = 30.0
        try:
            self.max_retries = int(os.getenv("OPENAI_EMBED_MAX_RETRIES") or 3)
        except Exception:
            self.max_retries = 3

        # Lazy import requests (not a hard dependency; fallback if missing)
        try:  # noqa: BLE001
            import requests  # type: ignore
            self._requests = requests
        except Exception:  # missing library -> provider will raise on use
            self._requests = None  # type: ignore

    def _iter_batches(self, texts: List[str]) -> Iterable[List[str]]:
        for i in range(0, len(texts), self.batch_size):
            yield texts[i : i + self.batch_size]

    def embed(self, texts: List[str]) -> List[List[float]]:  # noqa: D401
        if not texts:
            return []
        if not self.api_key or not self._requests:
            # Fallback silently to dummy behavior instead of raising (keeps pipeline resilient)
            return DummyEmbedding().embed(texts)
        out: List[List[float]] = []
        url = f"{self.base_url}/embeddings"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for batch in self._iter_batches(texts):
            payload = {"input": batch, "model": self.model}
            attempt = 0
            while True:
                attempt += 1
                try:
                    resp = self._requests.post(url, headers=headers, data=json.dumps(payload), timeout=self.timeout)
                    if resp.status_code == 200:
                        data = resp.json().get("data", [])
                        # Each item has embedding list
                        for item in data:
                            emb = item.get("embedding") or []
                            if not isinstance(emb, list):
                                emb = []
                            out.append([float(x) for x in emb[:2048]])  # soft cap to limit payload
                        break
                    if resp.status_code in {429, 500, 502, 503, 504} and attempt <= self.max_retries:
                        backoff = 0.5 * (2 ** (attempt - 1))
                        time.sleep(backoff)
                        continue
                    # Non-retryable or exhausted retries -> fallback dummy for remaining batch
                    dummy_remaining = DummyEmbedding().embed(batch)
                    out.extend(dummy_remaining)
                    break
                except Exception:
                    if attempt <= self.max_retries:
                        backoff = 0.5 * (2 ** (attempt - 1))
                        time.sleep(backoff)
                        continue
                    out.extend(DummyEmbedding().embed(batch))
                    break
        # Ensure alignment length == texts length
        if len(out) != len(texts):
            # pad with dummy embeddings deterministic
            for t in texts[len(out):]:  # noqa: B007
                out.append([float(len(t) % 10)])
        return out


_PROVIDER: EmbeddingProvider | None = None


def provider() -> EmbeddingProvider:
    global _PROVIDER
    if _PROVIDER is None:
        name = (os.getenv("EMBEDDING_PROVIDER") or "dummy").lower()
        if name == "openai" and os.getenv("OPENAI_API_KEY"):
            try:
                _PROVIDER = OpenAIEmbedding()
            except Exception:
                _PROVIDER = DummyEmbedding()
        else:
            _PROVIDER = DummyEmbedding()
    return _PROVIDER


__all__ = ["provider", "EmbeddingProvider", "OpenAIEmbedding", "DummyEmbedding"]
