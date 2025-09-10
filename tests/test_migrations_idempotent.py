import asyncio
import types
import time
import pytest

# We will mock the postgres module with in-memory capture of executed SQL
class MockPostgres:
    def __init__(self):
        self.executed = []
        self.rows_schema = set()
        # we simulate schema_migrations table contents
        self._migrations = set()

    async def execute(self, sql, *args):  # type: ignore
        self.executed.append((sql.strip(), args))
        # crude detection of insert into schema_migrations to record applied id
        if sql.lower().startswith("insert into schema_migrations"):
            self._migrations.add(args[0])
        return "OK"

    async def fetch(self, sql, *args):  # type: ignore
        if sql.lower().startswith("select id from schema_migrations"):
            return [(mid,) for mid in sorted(self._migrations)]
        return []

@pytest.mark.asyncio
async def test_migrations_idempotent(monkeypatch):
    monkeypatch.setenv("NEON_DATABASE_URL", "postgres://example")
    mock_pg = MockPostgres()
    monkeypatch.setitem(__import__("sys").modules, "storage.postgres", mock_pg)

    # Reload migrations after monkeypatch to ensure it binds mocked postgres
    import importlib
    import storage.migrations as mig
    mig = importlib.reload(mig)
    apply_migrations = mig.apply_migrations

    # First run should apply migrations (insert records + create tables)
    await apply_migrations()
    first_exec = list(mock_pg.executed)
    applied_ids = {args[0] for sql, args in first_exec if sql.lower().startswith("insert into schema_migrations")}
    assert applied_ids == {"0001_init_anomalies", "0002_calibration_quantiles"}

    # Clear executed log (but keep recorded migrations)
    mock_pg.executed.clear()

    # Second run should perform only idempotent CREATE TABLE IF NOT EXISTS + select + zero new inserts
    await apply_migrations()
    second_exec = list(mock_pg.executed)
    inserts_second = [c for c in second_exec if c[0].lower().startswith("insert into schema_migrations")]
    assert not inserts_second, f"Unexpected second-run migrations: {inserts_second}"
    # No further assertion needed; idempotency validated by absence of new inserts.
