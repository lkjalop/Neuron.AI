"""Asset feature extraction pipeline.

Produces per-asset aggregated metrics from current `findings` & `finding_events` tables
and writes rows into `asset_feature_snapshots` for modeling (anomaly detection, forecasting).
"""
from __future__ import annotations

import time
from typing import Dict, Any, List
from storage import postgres

SEVERITY_WEIGHTS = {
    'CRITICAL': 1.0,
    'HIGH': 0.7,
    'MEDIUM': 0.4,
    'LOW': 0.1,
    'INFO': 0.05
}


async def _fetch_open_findings():
    rows = await postgres.fetch("""
        SELECT asset_id, risk_severity, risk_score, risk_factors, first_seen, last_seen
        FROM findings WHERE state='open'
    """)
    return rows


async def _fetch_recent_events(win_24h: float, win_7d: float):
    rows = await postgres.fetch("""
        SELECT fe.finding_id, fe.event_type, fe.event_ts, fe.payload
        FROM finding_events fe
        WHERE fe.event_ts >= $1
    """, win_7d)
    recent_24h = [r for r in rows if r[2] >= win_24h]
    return rows, recent_24h


async def compute_asset_features(now: float | None = None) -> Dict[str, Dict[str, Any]]:
    now = now or time.time()
    win_24h = now - 24*3600
    win_7d = now - 7*24*3600
    open_rows = await _fetch_open_findings()
    all_events, recent_24h = await _fetch_recent_events(win_24h, win_7d)

    per_asset: Dict[str, Dict[str, Any]] = {}
    # Initialize base counts
    for asset_id, severity, risk_score, risk_factors, first_seen, last_seen in open_rows:
        asset_id = asset_id or 'unknown'
        a = per_asset.setdefault(asset_id, {
            'open_findings_total': 0,
            'open_critical': 0,
            'open_high': 0,
            'open_medium': 0,
            'open_low': 0,
            'exploit_exposed': 0,
            'exposure_score': 0.0,
            'new_findings_24h': 0,
            'closed_findings_24h': 0,
            'reopened_7d': 0,
            'age_total_hours': 0.0,
        })
        a['open_findings_total'] += 1
        sev_key = f"open_{(severity or 'LOW').lower()}"
        if sev_key in a:
            a[sev_key] += 1
        if risk_factors and isinstance(risk_factors, dict):
            if (risk_factors.get('exploit_available') or 0) > 0:
                a['exploit_exposed'] += 1
        a['exposure_score'] += SEVERITY_WEIGHTS.get(severity or 'LOW', 0.1)
        a['age_total_hours'] += (now - first_seen)/3600.0

    # Recent 24h events for new/closed
    # We assume event_type in payload; naive parse for state_change
    for finding_id, event_type, event_ts, payload in recent_24h:
        # payload is JSONB; may be dict or string
        p = payload if isinstance(payload, dict) else {}
        # We don't have asset_id directly; attempt join (simplify: skip for now)
        # TODO: optimize by prefetching finding->asset mapping if needed.
        pass

    # Compute averages & finalize
    for asset_id, vals in per_asset.items():
        if vals['open_findings_total'] > 0:
            vals['avg_age_open_hours'] = vals['age_total_hours'] / vals['open_findings_total']
        else:
            vals['avg_age_open_hours'] = 0.0
        vals['mttr_hours'] = None  # placeholder until remediation events tracked
        del vals['age_total_hours']
    return per_asset


async def persist_asset_feature_snapshots(feature_map: Dict[str, Dict[str, Any]], snapshot_ts: float | None = None):
    snapshot_ts = snapshot_ts or time.time()
    for asset_id, feat in feature_map.items():
        await postgres.execute(
            """
            INSERT INTO asset_feature_snapshots (
              asset_id, snapshot_ts, open_findings_total, open_critical, open_high, open_medium, open_low,
              exploit_exposed, exposure_score, new_findings_24h, closed_findings_24h, reopened_7d,
              avg_age_open_hours, mttr_hours
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
            ON CONFLICT (asset_id, snapshot_ts) DO NOTHING
            """,
            asset_id, snapshot_ts,
            feat.get('open_findings_total',0), feat.get('open_critical',0), feat.get('open_high',0),
            feat.get('open_medium',0), feat.get('open_low',0), feat.get('exploit_exposed',0),
            float(feat.get('exposure_score',0.0)), feat.get('new_findings_24h',0), feat.get('closed_findings_24h',0),
            feat.get('reopened_7d',0), feat.get('avg_age_open_hours',0.0), feat.get('mttr_hours')
        )


async def run_feature_snapshot():
    feats = await compute_asset_features()
    await persist_asset_feature_snapshots(feats)
    return feats

__all__ = ['compute_asset_features', 'persist_asset_feature_snapshots', 'run_feature_snapshot']
