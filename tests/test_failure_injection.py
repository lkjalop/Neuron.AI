import asyncio
import types

from core.ingest.manager import IngestionManager
from core import metrics


class FastSource:
    """Deterministic fast source yielding crafted events including invalid ones."""
    def __init__(self):
        self.emitted = 0

    async def stream(self):  # async generator
        for i in range(200):
            # cycle: good, invalid tenant, malformed (missing tenant), good
            kind = i % 4
            if kind == 0:
                yield {"tenant_id": "t1", "features": {"v": i}}
            elif kind == 1:
                yield {"tenant_id": "bad", "features": {"v": i}}
            elif kind == 2:
                yield {"features": {"v": i}}  # missing tenant -> unknown error path
            else:
                yield {"tenant_id": "t1", "features": {"v": i}}


async def run_manager(mgr: IngestionManager, duration: float = 0.05):
    await mgr.start()
    await asyncio.sleep(duration)
    await mgr.stop()


def get_counter(metric, *labels):
    return metric.labels(*labels)._value.get()


def test_failure_modes_trigger_metrics():
    # small queue & very low rate limiter capacity to trigger rate_limit and queue_full
    mgr = IngestionManager(["t1"], queue_max=5, rate_capacity=2, rate_fill=0.1)
    # monkeypatch source
    mgr.source = FastSource()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_manager(mgr, 0.05))

    # Expect some invalid tenant errors
    invalid_tenant_errors = get_counter(metrics.INGEST_ERRORS_TOTAL, "invalid_tenant")
    assert invalid_tenant_errors > 0, "Should record invalid tenant errors"

    # Unknown or validation errors likely > 0 (missing tenant id path -> unknown)
    # Accept either bucket having counts
    validation_errors = get_counter(metrics.INGEST_ERRORS_TOTAL, "validation")
    unknown_errors = get_counter(metrics.INGEST_ERRORS_TOTAL, "unknown")
    assert (validation_errors + unknown_errors) > 0, "Should have validation or unknown errors"

    # Dropped events for rate_limit or queue_full
    rate_limit_drops = 0
    queue_full_drops = 0
    # Iterate through collected samples in registry to sum labeled counters
    # Direct label fetch may raise if never created; guard with try/except
    try:
        rate_limit_drops = get_counter(metrics.EVENTS_DROPPED_TOTAL, "t1", "rate_limit")
    except Exception:
        pass
    try:
        queue_full_drops = get_counter(metrics.EVENTS_DROPPED_TOTAL, "t1", "queue_full")
    except Exception:
        pass
    assert (rate_limit_drops + queue_full_drops) > 0, "Should have drop events from rate limit or queue full"
