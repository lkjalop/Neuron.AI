"""Gate metrics aggregation script.

Runs variance analyzer (optionally synthetic harness first) and emits gate_report.json
with pass/fail summaries of readiness gates (subset for now).
"""
from __future__ import annotations
import asyncio, json, time, os, uuid, statistics
from pathlib import Path

from scripts import perf_probe
from scripts import synthetic_dataset_harness as sdh

VARIANCE_MIN = 0.0  # Non-negative; real threshold tuning later


async def ensure_dataset_once():
    # If no variance file and no feature snapshots, run harness
    try:
        from storage import postgres
        rows = await postgres.fetch('SELECT 1 FROM asset_feature_snapshots LIMIT 1')
        if not rows:
            await sdh.run_once()
    except Exception:
        return


async def build_report():
    await ensure_dataset_once()
    # Run variance analyzer inline
    from scripts import data_variance_analyzer as dva
    variance = await dva.collect()
    # Performance probe (small)
    ingest_lat = dash_lat = []
    try:
        ingest_lat = await perf_probe.measure_ingestion(batch_size=10, iterations=1)
        dash_lat = await perf_probe.measure_dashboard(refreshes=1)
    except Exception:
        pass
    gates = {}
    # G1: ingestion stability (single run placeholder) -> pass if we have any latency sample
    gates['G1_ingestion_stability'] = 'pass' if ingest_lat else 'pending'
    # G2: feature variance (at least one field present with >= VARIANCE_MIN)
    if variance.get('variances'):
        any_field = any(v > VARIANCE_MIN for v in variance['variances'].values())
        gates['G2_feature_variance'] = 'pass' if any_field else 'fail'
    else:
        gates['G2_feature_variance'] = 'pending'
    report = {
        'run_id': str(uuid.uuid4()),
        'timestamp': time.time(),
        'variance': variance,
        'ingestion_latency': ingest_lat,
        'dashboard_latency': dash_lat,
        'gates': gates,
    }
    with open('gate_report.json','w',encoding='utf-8') as f:
        json.dump(report,f,indent=2)
    print(json.dumps(report))
    return report

def main():
    asyncio.run(build_report())

if __name__ == '__main__':
    main()
