"""Simple DB layer (SQLite default; Postgres if DATABASE_URL provided)."""
from __future__ import annotations
import os, sqlite3, time, json, contextlib
from typing import Iterator, Any, Dict

_DB_URL = os.getenv("DATABASE_URL")  # e.g. postgres://... (not implemented yet)
_SQLITE_PATH = os.getenv("SQLITE_PATH", "neuron.db")

# For now only SQLite; placeholder interface to swap for SQLAlchemy later.

def get_connection():
    if _DB_URL:
        raise NotImplementedError("Postgres backend pending integration")
    conn = sqlite3.connect(_SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@contextlib.contextmanager
def session() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# Basic helpers

def upsert_asset(asset_id: str, tenant: str, type_: str | None, meta: Dict[str, Any]):
    now = time.time()
    with session() as s:
        s.execute("""
        INSERT INTO assets(id, tenant, type, meta, created_ts, updated_ts)
        VALUES(?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET tenant=excluded.tenant, type=excluded.type, meta=excluded.meta, updated_ts=excluded.updated_ts
        """, (asset_id, tenant, type_, json.dumps(meta), now, now))


def record_finding(fid: str, tenant: str, cve: str | None, severity: str | None, status: str, risk_json: Dict[str, Any]):
    now = time.time()
    with session() as s:
        s.execute("""
        INSERT INTO findings(id, tenant, cve, severity, status, risk_json, discovered_ts, updated_ts)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET status=excluded.status, risk_json=excluded.risk_json, updated_ts=excluded.updated_ts
        """, (fid, tenant, cve, severity, status, json.dumps(risk_json), now, now))

__all__ = ["session", "upsert_asset", "record_finding"]
