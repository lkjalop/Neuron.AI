"""Spike injector utility.

Creates a synthetic spike in exposure for a chosen asset by inserting a burst
of CRITICAL findings. Intended for anomaly detection ground truth labeling.
"""
from __future__ import annotations
import asyncio, time, uuid
from storage import postgres


async def inject(asset_id: str = 'asset-spike', count: int = 5):
    now = time.time()
    for i in range(count):
        fid = f"spike-{asset_id}-{i}-{uuid.uuid4().hex[:6]}"
        await postgres.execute(
            """INSERT INTO findings (id,cve_id,asset_id,component_id,first_seen,last_seen,state,detection_source,risk_score,risk_severity,asset_metadata,sla_due_ts,risk_factors,treatment_state,accepted_risk,remediation_target_ts)
            VALUES ($1,$2,$3,$4,$5,$5,'open','spike',0.99,'CRITICAL','{}',NULL,'{}',NULL,NULL,NULL)
            ON CONFLICT DO NOTHING""",
            fid, f"CVE-SPIKE-{i}", asset_id, None, now
        )
    return {'asset_id': asset_id, 'inserted': count, 'ts': now}


def main():
    import argparse, json
    ap = argparse.ArgumentParser()
    ap.add_argument('--asset', default='asset-spike')
    ap.add_argument('--count', type=int, default=5)
    args = ap.parse_args()
    res = asyncio.run(inject(args.asset, args.count))
    print(res)

if __name__ == '__main__':
    main()
