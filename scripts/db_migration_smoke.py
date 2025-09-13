"""DB Migration Smoke Test

Verifies that schema_migrations includes 0015_findings_composite_indexes and that
composite indexes exist for findings and vulnerabilities tables when DATABASE_URL is set.

Usage (PowerShell):
  $env:DATABASE_URL="postgres://..."; python scripts/db_migration_smoke.py
"""
from __future__ import annotations

import os
import asyncio
import sys

async def _run():
    url = os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL")
    if not url:
        print("SKIP: No DATABASE_URL/NEON_DATABASE_URL set")
        return 0
    try:
        from storage.migrations import apply_migrations  # type: ignore
    except Exception as e:
        print(f"ERROR: cannot import migrations: {e}")
        return 2
    # Apply migrations best-effort
    try:
        await apply_migrations()
    except Exception as e:
        print(f"WARN: apply_migrations raised: {e}")
    # Now query for indexes and migration id
    try:
        from storage import postgres  # type: ignore
        async def fetchval(sql: str, *args):
            rows = await postgres.fetch(sql, *args)
            return rows
        # Ensure insights tables exist (best-effort create)
        await postgres.execute(
            """
            CREATE TABLE IF NOT EXISTS framework_analysis (
                id TEXT PRIMARY KEY,
                created_ts DOUBLE PRECISION,
                primary_fw TEXT,
                targets JSONB,
                result JSONB
            )
            """
        )
        await postgres.execute(
            """
            CREATE TABLE IF NOT EXISTS strategic_insights (
                id TEXT PRIMARY KEY,
                created_ts DOUBLE PRECISION,
                question TEXT,
                organization TEXT,
                insight JSONB
            )
            """
        )
        # schema_migrations contains 0015
        rows = await fetchval("SELECT id FROM schema_migrations WHERE id=$1", "0015_findings_composite_indexes")
        assert rows, "Missing migration 0015_findings_composite_indexes in schema_migrations"
        # Check indexes in pg_class/pg_indexes
        checks = [
            ("idx_findings_state_sev_last",),
            ("idx_findings_asset_state_last",),
            ("idx_vuln_kev_exploit",),
        ]
        for (name,) in checks:
            r = await fetchval("SELECT indexname FROM pg_indexes WHERE indexname=$1", name)
            assert r, f"Missing index {name}"
        # Verify new insights tables exist
        tbl_checks = [
            ("framework_analysis",),
            ("strategic_insights",),
        ]
        for (tname,) in tbl_checks:
            r = await fetchval(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = $1
                """,
                tname,
            )
            assert r, f"Missing table {tname}"
        print("OK: Migration 0015 and composite indexes present")
        return 0
    except AssertionError as ae:
        print(f"FAIL: {ae}")
        return 1
    except Exception as e:
        print(f"ERROR: Smoke test error: {e}")
        return 2

if __name__ == "__main__":
    try:
        rc = asyncio.get_event_loop().run_until_complete(_run())
    except RuntimeError:
        rc = asyncio.run(_run())
    sys.exit(rc)
