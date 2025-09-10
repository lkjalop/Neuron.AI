# Scaling Architecture Roadmap

This document outlines a staged scaling plan for the Neuron ingestion & processing pipeline. Each stage deliberately minimizes complexity while creating clear, measurable upgrade points.

## Goals
- Maintain low ingestion latency (p95 < target) while increasing event throughput.
- Preserve correctness & detection fidelity during scaling.
- Provide incremental deployment steps & rollback clarity.
- Keep operational costs predictable.

## Stage 0 (Today – In-Process Queue)
Current model uses an in-memory queue bound to a single FastAPI process (optionally multi-worker via uvicorn/gunicorn, but each has its own queue). Characteristics:
- Pros: Simplicity, zero external deps, very low overhead.
- Cons: Backpressure isolated per worker, uneven load distribution, limited horizontal elasticity, queue loss on restart.
- Bottlenecks observed/predicted: Python GIL contention in detector loop under high concurrency, single-process memory growth, lack of ingestion surge smoothing.

## Stage 1 (Unified Pluggable Ingestion Interface)
Introduce `IngestionBackend` abstraction with interchangeable implementations:
- `InMemoryBackend` (baseline): wraps `asyncio.Queue`.
- `RedisBackend` (stub initially): provides a shared queue semantics using Redis list / stream.

Selection via env var: `INGEST_BACKEND` = `memory` (default) or `redis`.

Acceptance Criteria:
- All enqueue/dequeue operations routed through interface.
- Fast path inline detection unaffected.
- Graceful fallback to memory if Redis unavailable.

Risk Mitigation:
- Redis backend initially optional; errors fall back with warning metric/log.
- Add metric: `ingest_backend_active{name=..}` gauge.

## Stage 2 (External Queue + Worker Pool)
Enhance Redis backend to production-grade semantics:
- Use Redis Streams (XADD / XREADGROUP) or Lists with blocking pop for worker consumption.
- Dedicated async worker processes separate from API serving pods.
- Visibility Timeout & Retry (dead-letter) semantics added.

Operational Additions:
- Metrics: pending length, ack latency, redelivery count.
- Health endpoints: `/ingest/queue_depth`, `/ingest/lag`.

Deployment Pattern:
1. Deploy Redis.
2. Enable dual-writing (memory + redis) in shadow mode.
3. Validate metrics parity & detection output.
4. Switch primary consumers to worker deployment.

Rollback: flip flag to memory only; workers drain in-flight, then terminate.

## Stage 3 (Horizontal Sharding & Multi-Tenant Partitioning)
Motivation: isolate noisy tenants & reduce cross-tenant contention.

Sharding Strategies:
- Hash-based partition on `tenant_id` -> queue shard.
- Dynamic weighting: heavy tenants migrated to dedicated shard.
- Optional region-based segmentation (future multi-region DR).

Additions:
- Shard Router component (stateless hash ring).
- Rebalancing tool (moves slice of tenant hash space, coordinates with workers).
- Metrics: `shard_queue_depth{shard=}`, `shard_lag_seconds{shard=}`.

Data Integrity Safeguards:
- Idempotency keys for events to avoid duplication on rebalance.
- Drain & cut-over sequence with watermark barrier.

## Stage 4 (Advanced Optimizations)
- Batch pull & vectorized detection passes.
- C extensions / Rust for hotspots (detector pipeline).
- Zero-copy JSON ingestion (orjson / msgpack ingress option).
- Async I/O offload for network-bound enrichment calls.

## Metrics & SLOs
| Dimension | SLI | Target | Alerting |
|-----------|-----|--------|----------|
| Ingest Latency | p95 ms (ingest->enqueue) | < 20ms Stage1, < 30ms Stage2, < 40ms Stage3 | Warning at 1.5x, Critical at 2x |
| Detector Processing | p95 ms per event | < 120ms | Degradation >30% over baseline |
| Queue Depth | max pending | < 5k per shard | Critical if >20k |
| Queue Lag | oldest age | < 5s | Critical if >20s |
| Event Loss | dropped / total | 0% sustained | Any sustained >0.1% |

## Configuration Flags
| Flag | Stage | Description |
|------|-------|-------------|
| `INGEST_BACKEND` | 1+ | `memory` or `redis` |
| `INGEST_DUAL_WRITE` | 2 | Write to both memory & redis for shadow validation |
| `INGEST_SHARD_COUNT` | 3 | Number of logical shards |
| `INGEST_SHARD_MODE` | 3 | `hash` (future: `weighted`) |

## Logging & Observability Enhancements
- Add structured log fields: `ingest.backend`, `ingest.enqueue_ms`, `queue.shard`.
- Trace spans (future): `ingest.parse`, `ingest.enqueue`, `detect.run`.

## Risk Register
| Risk | Stage | Mitigation |
|------|-------|------------|
| Redis outage stalls ingestion | 1-2 | Fallback to memory; circuit breaker & metric |
| Shard imbalance hotspots | 3 | Periodic rebalance analyzer |
| Detector CPU saturation | 0-4 | Inline profiling + offload / batching |
| Event duplication on cutover | 2-3 | Idempotency keys + watermark barrier |

## Rollout Playbook (Example Stage1->2)
1. Deploy Redis; set `INGEST_BACKEND=memory`, `INGEST_DUAL_WRITE=1`.
2. Enable dual-write code path; monitor parity metrics 24h.
3. Start worker deployment (consuming redis) in shadow (no side-effects) verify detection parity logs.
4. Flip primary consumer to workers; keep dual-write for 2h.
5. Disable dual-write; scale API pods horizontally.
6. Record new perf baseline & update README/CHANGELOG.

## Future Considerations
- Multi-region active-active replication (Redis streams mirror or Kafka migration).
- Adaptive autoscaling on queue depth & p95 latency.
- Security isolation: per-tenant encryption at rest for queued payloads.

---
Document version: 1.0 (initial draft)
