"""Performance probe scripts.

Measures ingestion -> persistence latency and dashboard aggregation time over N iterations.
"""
from __future__ import annotations

import asyncio, time, statistics as stats
from core.ingest.connectors.qualys import QualysConfig, qualys_stream
from core.ingest.connectors.persistence import persist_vuln_event
from dashboard.aggregator import refresh_dashboard


async def measure_ingestion(batch_size=100, iterations=3):
    latencies = []
    for _ in range(iterations):
        cfg = QualysConfig(batch_size=batch_size)
        start = time.time()
        async for ev in qualys_stream(cfg):
            await persist_vuln_event(ev)
        latencies.append(time.time() - start)
    return latencies


async def measure_dashboard(refreshes=3):
    times = []
    for _ in range(refreshes):
        t0 = time.time()
        await refresh_dashboard()
        times.append(time.time() - t0)
    return times


async def run():
    ing = await measure_ingestion()
    dash = await measure_dashboard()
    print({
        'ingestion_sec': ing,
        'ingestion_sec_stats': {'avg': stats.mean(ing), 'p95': sorted(ing)[int(0.95*len(ing))-1]},
        'dashboard_sec': dash,
        'dashboard_sec_stats': {'avg': stats.mean(dash), 'p95': sorted(dash)[int(0.95*len(dash))-1]},
    })


def main():
    asyncio.run(run())


if __name__ == '__main__':
    main()
