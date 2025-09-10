from __future__ import annotations
import time, sqlite3, os, json
from typing import Dict, Any, List
from ingest.base import build_connector
from core.metrics import INGEST_SOURCE_LAG_SECONDS, INGEST_SOURCE_ACTIVE

_SQLITE_PATH = os.getenv("SQLITE_DB_PATH", "artifacts/neuron.db")

def _persist_events(source_id: str, tenant_id: str | None, project_id: str | None, items: List[Dict[str, Any]]):
    try:
        cx = sqlite3.connect(_SQLITE_PATH)
        cx.execute("CREATE TABLE IF NOT EXISTS ingestion_events (event_id TEXT PRIMARY KEY, source_id TEXT, tenant_id TEXT, project_id TEXT, received_at REAL, raw_ref TEXT, size_bytes INTEGER)")
        for it in items:
            eid = f"{source_id}:{int(time.time()*1000)}:{hash(json.dumps(it, sort_keys=True)) & 0xffff}"  # pragmatic uniqueness
            cx.execute("INSERT OR IGNORE INTO ingestion_events VALUES (?,?,?,?,?,?,?)", (
                eid,
                source_id,
                tenant_id,
                project_id,
                time.time(),
                json.dumps(it)[:8000],
                len(json.dumps(it)),
            ))
        cx.commit(); cx.close()
    except Exception:
        pass


def poll_once(source_def: Dict[str, Any]):
    """Poll a single source definition.
    source_def schema suggestion: {id, type, config, tenant_id, project_id}
    """
    source_id = source_def["id"]
    kind = source_def["type"]
    cfg = source_def.get("config", {})
    tenant_id = source_def.get("tenant_id")
    project_id = source_def.get("project_id")
    start = time.time()
    connector = build_connector(kind, source_id, cfg)
    raw_items = connector.poll() or []
    active = 1 if raw_items else 0
    lag = time.time() - start
    try:
        INGEST_SOURCE_LAG_SECONDS.labels(source=source_id).set(lag)
        INGEST_SOURCE_ACTIVE.labels(source=source_id).set(active)
    except Exception:
        pass
    norm_items = [connector.normalize(r) for r in raw_items]
    if norm_items:
        _persist_events(source_id, tenant_id, project_id, norm_items)
    return {"source": source_id, "count": len(norm_items), "lag": lag}
