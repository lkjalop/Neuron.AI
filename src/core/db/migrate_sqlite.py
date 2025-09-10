"""Lightweight SQLite migration runner.

Applies .sql files in the top-level `migrations/` directory (lexicographic order) to a
SQLite database path provided via env `SQLITE_DB_PATH` (default `artifacts/neuron.db`).

Each migration runs inside its own transaction. A table `_migrations` is created to
track applied filenames. Idempotent: already applied filenames are skipped.

Intentionally minimal—does not attempt locking or checksum verification. Suitable
for local developer evaluation; production paths should use Postgres migrations.
"""
from __future__ import annotations
import os, sqlite3, glob, pathlib, logging

log = logging.getLogger("migrate_sqlite")

def _db_path() -> str:
    return os.getenv("SQLITE_DB_PATH", "artifacts/neuron.db")

def apply_sqlite_migrations() -> dict:
    path = _db_path()
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS _migrations (filename TEXT PRIMARY KEY, applied_ts REAL DEFAULT (strftime('%s','now')))" )
    cur = conn.cursor()
    cur.execute("SELECT filename FROM _migrations")
    applied = {r[0] for r in cur.fetchall()}
    mig_dir = pathlib.Path("migrations")
    if not mig_dir.exists():
        return {"applied": len(applied), "new": 0, "skipped": 0, "path": path}
    files = sorted(glob.glob(str(mig_dir / "*.sql")))
    new = 0; skipped = 0
    for f in files:
        name = os.path.basename(f)
        if name in applied:
            skipped += 1
            continue
        sql = pathlib.Path(f).read_text(encoding="utf-8")
        try:
            with conn:
                conn.executescript(sql)
                conn.execute("INSERT INTO _migrations (filename) VALUES (?)", (name,))
            new += 1
            log.info("Applied migration %s", name)
        except Exception:
            log.exception("Migration failed %s", name)
            raise
    return {"applied": len(applied)+new, "new": new, "skipped": skipped, "path": path}

__all__ = ["apply_sqlite_migrations"]
