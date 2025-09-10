"""Dashboard aggregation scaffolding.

Computes:
 - vulnerability severity distribution
 - exploit availability counts
 - open findings by risk_severity
 - trends (7d new vs closed) if timestamps available

Persists snapshot in `dashboard_cache` table keyed by snapshot_type='main'.
"""
from __future__ import annotations

import time, json
from typing import Dict, Any
from storage import postgres


async def compute_snapshot() -> Dict[str, Any]:
    # Vulnerability severities
    sev_rows = await postgres.fetch("SELECT severity, count(*) FROM vulnerabilities GROUP BY severity")
    exploit_rows = await postgres.fetch("SELECT exploit_available, count(*) FROM vulnerabilities GROUP BY exploit_available")
    finding_rows = await postgres.fetch("SELECT risk_severity, count(*) FROM findings WHERE state='open' GROUP BY risk_severity")
    # Trend (new vs closed last 7d) naive placeholder: uses findings first_seen/last_seen deltas
    now = time.time()
    seven_days = now - 7*86400
    new_rows = await postgres.fetch("SELECT count(*) FROM findings WHERE first_seen >= $1", seven_days)
    closed_rows = await postgres.fetch("SELECT count(*) FROM finding_events WHERE event_type='state_change' AND payload::text LIKE '%\"to\": \"closed\"%' AND event_ts >= $1", seven_days)
    snapshot = {
        'vulnerability_severity': { (r[0] or 'UNKNOWN'): r[1] for r in sev_rows },
        'vulnerability_exploit_available': { str(r[0]): r[1] for r in exploit_rows },
        'open_findings_severity': { (r[0] or 'UNKNOWN'): r[1] for r in finding_rows },
        'new_findings_7d': new_rows[0][0] if new_rows else 0,
        'closed_findings_7d': closed_rows[0][0] if closed_rows else 0,
        'generated_ts': now,
    }
    return snapshot


async def persist_snapshot(snapshot: Dict[str, Any]) -> None:
    await postgres.execute(
        """
        INSERT INTO dashboard_cache (snapshot_type, generated_ts, data)
        VALUES ($1,$2,$3)
        ON CONFLICT (snapshot_type) DO UPDATE SET
          generated_ts=EXCLUDED.generated_ts,
          data=EXCLUDED.data
        """,
        'main',
        snapshot['generated_ts'],
        json.dumps(snapshot),
    )


async def refresh_dashboard() -> Dict[str, Any]:
    snap = await compute_snapshot()
    await persist_snapshot(snap)
    return snap

__all__ = ['compute_snapshot', 'persist_snapshot', 'refresh_dashboard']
