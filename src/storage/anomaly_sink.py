"""Asynchronous batched anomaly persistence + TTL pruning.

Design:
 - Producers enqueue anomaly dicts via `enqueue(anomaly_dict)`.
 - Background task flushes in batches (runtime params control size & interval).
 - TTL pruning executed opportunistically after flush when due.
 - Depends on schema created by migrations (anomalies table + index on event_time).
 - Graceful no-op if Postgres not configured or asyncpg missing.
"""
from __future__ import annotations

import os, asyncio, json, time, uuid
from typing import List, Dict, Any, Optional
from config import runtime_params
from core import metrics

_SINK: 'AnomalySink' | None = None

class AnomalySink:
    def __init__(self):
        self._queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=5000)
        self._task: Optional[asyncio.Task] = None
        self._last_prune: float = 0.0
        self._failures: int = 0
        self._circuit_open_until: float = 0.0

    def started(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self):
        if self.started():
            return
        if not (os.getenv("NEON_DATABASE_URL") or os.getenv("DATABASE_URL")):
            return  # DB not configured
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._run())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:  # noqa: BLE001
                pass
            self._task = None

    def enqueue(self, rec: Dict[str, Any]):
        if not self.started():
            return
        # Circuit breaker drop if open
        if time.time() < self._circuit_open_until:
            return
        try:
            self._queue.put_nowait(rec)
        except Exception:
            pass

    async def flush_once(self):  # exposed for tests
        batch = []
        while len(batch) < self._batch_size():
            try:
                batch.append(self._queue.get_nowait())
            except Exception:
                break
        if batch:
            await self._persist_with_retry(batch)
        await self._maybe_prune()
        try:
            metrics.ANOMALY_SINK_QUEUE_DEPTH.set(self._queue.qsize())  # type: ignore[attr-defined]
        except Exception:
            pass

    async def _run(self):
        while True:
            try:
                await asyncio.sleep(self._interval())
                await self.flush_once()
            except asyncio.CancelledError:
                break
            except Exception:
                continue

    def _batch_size(self) -> int:
        try:
            v = int(runtime_params.get_param("anomalies.batch.size") or 50)
            return min(max(v, 1), 500)
        except Exception:
            return 50

    def _interval(self) -> float:
        try:
            v = float(runtime_params.get_param("anomalies.batch.interval_s") or 2.0)
            return max(0.1, min(v, 30.0))
        except Exception:
            return 2.0

    def _ttl_days(self) -> int:
        try:
            v = int(runtime_params.get_param("anomalies.ttl_days") or 7)
            return max(1, min(v, 365))
        except Exception:
            return 7

    async def _persist(self, batch: List[Dict[str, Any]]):
        try:
            from storage import postgres  # type: ignore
        except Exception:
            return
        try:
            # Build multi-row insert using parameter placeholders indexing not supported easily with asyncpg dynamic; insert row by row (batch small)
            for rec in batch:
                try:
                    rid = rec.get('id') or str(uuid.uuid4())
                    tenant = rec.get('tenant') or 'unknown'
                    detector = rec.get('detector') or rec.get('source') or 'unknown'
                    score = float(rec.get('score') or rec.get('activity') or 0.0)
                    fscore = float(rec.get('fusion_decision_score') or 0.0)
                    ts_val = float(rec.get('event_time') or rec.get('timestamp') or time.time())
                    start = time.time()
                    await postgres.execute(
                        "INSERT INTO anomalies (id, tenant, detector, score, fusion_score, event_time, payload) VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (id) DO NOTHING",
                        rid, tenant, detector, score, fscore, ts_val, json.dumps(rec)
                    )
                    try:
                        metrics.ANOMALY_SINK_PERSIST_LATENCY.observe(time.time() - start)  # type: ignore[attr-defined]
                    except Exception:
                        pass
                except Exception:
                    continue
        except Exception:
            return

    async def _persist_with_retry(self, batch: List[Dict[str, Any]]):
        attempts = 0
        max_attempts = 3
        base_delay = 0.05
        while attempts < max_attempts:
            try:
                await self._persist(batch)
                try:
                    metrics.ANOMALY_SINK_FLUSH_TOTAL.labels(outcome="success").inc()  # type: ignore[attr-defined]
                except Exception:
                    pass
                self._failures = 0
                return
            except Exception:
                attempts += 1
                if attempts >= max_attempts:
                    try:
                        metrics.ANOMALY_SINK_FLUSH_TOTAL.labels(outcome="failure").inc()  # type: ignore[attr-defined]
                    except Exception:
                        pass
                    self._failures += 1
                    if self._failures >= 5:  # open circuit
                        self._circuit_open_until = time.time() + min(60, 2 ** min(6, self._failures))
                    return
                await asyncio.sleep(base_delay * (2 ** (attempts - 1)))

    async def _maybe_prune(self):
        now = time.time()
        if (now - self._last_prune) < 300:  # every 5 minutes
            return
        self._last_prune = now
        ttl_days = self._ttl_days()
        cutoff = now - (ttl_days * 86400)
        try:
            from storage import postgres  # type: ignore
            await postgres.execute("DELETE FROM anomalies WHERE event_time < $1", cutoff)
        except Exception:
            return


def sink() -> AnomalySink:
    global _SINK
    if _SINK is None:
        _SINK = AnomalySink()
    return _SINK

__all__ = ["sink", "AnomalySink"]