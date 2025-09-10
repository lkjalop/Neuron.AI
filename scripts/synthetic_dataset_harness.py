"""Synthetic dataset harness.

Runs synthetic Qualys, Tenable, and SIEM streams, persists vulnerability findings,
refreshes dashboard, feature snapshots, and exports a dataset manifest for modeling.
"""
from __future__ import annotations

import asyncio, json, time, uuid
from core.ingest.connectors.qualys import QualysConfig, qualys_stream
from core.ingest.connectors.tenable import TenableConfig, tenable_stream
from core.ingest.connectors.siem import SIEMConfig, siem_stream
from core.ingest.connectors.persistence import persist_vuln_event
from dashboard.aggregator import refresh_dashboard
from features.asset_features import run_feature_snapshot
from storage import postgres


async def _drain(stream, persist=True):
    count = 0
    async for ev in stream:
        count += 1
        if persist and ev.get('event_type','').startswith('vuln'):
            await persist_vuln_event(ev)
    return count


async def run_once():
    qcfg = QualysConfig(batch_size=50)
    tcfg = TenableConfig(batch_size=40)
    scfg = SIEMConfig(batch_size=30)
    totals = {}
    totals['qualys_events'] = await _drain(qualys_stream(qcfg))
    totals['tenable_events'] = await _drain(tenable_stream(tcfg))
    totals['siem_events'] = await _drain(siem_stream(scfg), persist=False)
    snap = await refresh_dashboard()
    feats = await run_feature_snapshot()
    manifest = {
        'run_id': str(uuid.uuid4()),
        'generated_ts': time.time(),
        'event_counts': totals,
        'dashboard_keys': list(snap.keys()),
        'asset_feature_rows': len(feats),
    }
    print(json.dumps(manifest, indent=2))


def main():
    asyncio.run(run_once())


if __name__ == '__main__':
    main()
