from __future__ import annotations
import os, sqlite3, time
from typing import Dict

_SQLITE_PATH = os.getenv("SQLITE_DB_PATH", "artifacts/neuron.db")

# Age-based pruning for domain tables; returns counts purged per table.
# Tables expected: detection(ts), ioc(last_seen), flow(last_seen)

def prune_domain_tables(max_age_hours: float | None = None) -> Dict[str,int]:
    if max_age_hours is None:
        try:
            max_age_hours = float(os.getenv("DOMAIN_RETENTION_MAX_AGE_H", "0")) or None
        except Exception:
            max_age_hours = None
    if max_age_hours is None:
        return {"skipped": 1}
    cutoff = time.time() - max_age_hours * 3600
    removed: Dict[str,int] = {}
    try:
        cx = sqlite3.connect(_SQLITE_PATH)
        cur = cx.cursor()
        for tbl, col in ("detection","ts"), ("ioc","last_seen"), ("flow","last_seen"):
            try:
                cur.execute(f"DELETE FROM {tbl} WHERE {col} < ?", (cutoff,))
                removed[tbl] = cur.rowcount
            except Exception:
                continue
        cx.commit(); cx.close()
    except Exception:
        pass
    return removed

__all__ = ["prune_domain_tables"]
