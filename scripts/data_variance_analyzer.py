"""Data variance analyzer.

Computes variance and basic sparsity metrics for asset_feature_snapshots.
Outputs JSON to stdout and writes variance_report.json.
"""
from __future__ import annotations
import asyncio, json, statistics, os
from storage import postgres

NUMERIC_FIELDS = [
    'open_findings_total','open_critical','open_high','open_medium','open_low',
    'exploit_exposed','exposure_score','new_findings_24h','closed_findings_24h'
]

async def collect():
    try:
        rows = await postgres.fetch('SELECT * FROM asset_feature_snapshots LIMIT 2000')
    except Exception:
        return {'error':'table_missing','variances':{}}
    if not rows:
        return {'error':'no_rows','variances':{}}
    # asyncpg Records behave mapping-like
    variances = {}
    for field in NUMERIC_FIELDS:
        vals = []
        for r in rows:
            try:
                vals.append(float(r[field]))
            except Exception:
                pass
        if len(vals) > 1:
            try:
                variances[field] = statistics.pvariance(vals)
            except Exception:
                variances[field] = 0.0
        elif vals:
            variances[field] = 0.0
    return {'count': len(rows), 'variances': variances}

async def run():
    data = await collect()
    path = 'variance_report.json'
    with open(path,'w',encoding='utf-8') as f:
        json.dump(data,f,indent=2)
    print(json.dumps(data))
    return data

def main():
    asyncio.run(run())

if __name__ == '__main__':
    main()
