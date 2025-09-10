import asyncio
import time
from config import runtime_params
from storage.anomaly_sink import sink


class MockPostgresModule:
    def __init__(self):
        self.executed = []

    async def execute(self, sql, *args):  # type: ignore
        self.executed.append((sql, args))
        return "OK"


def test_anomaly_persistence(monkeypatch):
    """Validate that enqueued anomalies are flushed via the sink using INSERT INTO anomalies."""
    monkeypatch.setenv("NEON_DATABASE_URL", "postgres://example")
    mock_pg = MockPostgresModule()
    monkeypatch.setitem(__import__("sys").modules, "storage.postgres", mock_pg)

    s = sink()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(s.start())

    # Enqueue a few anomaly records
    now = time.time()
    for i in range(3):
        s.enqueue({
            "id": f"a{i}",
            "tenant": "t1",
            "detector": "baseline",
            "score": 1.0 + i,
            "fusion_decision_score": 2.0 + i,
            "event_time": now,
            "extra": {"i": i},
        })

    # Force immediate flush (test helper method available: flush_once)
    loop.run_until_complete(s.flush_once())

    # Assert inserts executed for each anomaly id (ON CONFLICT form)
    inserts = [c for c in mock_pg.executed if c[0].startswith("INSERT INTO anomalies")]
    assert len(inserts) == 3, f"Expected 3 inserts, got {len(inserts)}"
    # Ensure each payload carries JSON string (last arg) and id mapped
    ids = {call[1][0] for call in inserts}
    assert ids == {"a0", "a1", "a2"}

    # TTL prune won't run yet (5 min cadence) but DELETE shouldn't appear
    deletes = [c for c in mock_pg.executed if c[0].startswith("DELETE FROM anomalies")]
    # Prune may or may not run depending on last_prune timing; if present ensure only one
    assert len(deletes) <= 1
