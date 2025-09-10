"""Performance harness scaffold.

Goals:
 - Measure baseline request latency for key endpoints.
 - Generate synthetic governance recommendation load.
 - Measure ingestion throughput (events/sec) baseline.
 - Future: normalization mapping update frequency & memory footprint.

Outputs JSON metrics to artifacts/perf/perf_run_<timestamp>.json
"""
from __future__ import annotations
import time, json, pathlib, statistics, datetime
import threading
from typing import Callable, List, Tuple
import argparse

import requests

DEFAULT_BASE_URL = 'http://127.0.0.1:8000'
ROOT = pathlib.Path(__file__).resolve().parents[1]
ART = ROOT / 'artifacts' / 'perf'
ART.mkdir(parents=True, exist_ok=True)

DEFAULT_ENDPOINTS: List[Tuple[str,str]] = [
    ('diagnostics', '/diagnostics/config'),
    ('governance_recent', '/governance/recommendations/recent'),
]

def time_endpoint(base_url: str, path: str, samples: int) -> list[float]:
    latencies = []
    url = base_url + path
    for _ in range(samples):
        t0 = time.perf_counter()
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        latencies.append((time.perf_counter() - t0) * 1000.0)
    return latencies

def worker(fn: Callable[[], None]):
    fn()

def parse_args():
    ap = argparse.ArgumentParser(description='Performance harness')
    ap.add_argument('--base-url', default=DEFAULT_BASE_URL)
    ap.add_argument('--samples', type=int, default=20)
    ap.add_argument('--concurrency', type=int, default=4)
    ap.add_argument('--ingest-events', type=int, default=500)
    ap.add_argument('--ingest-batch-size', type=int, default=25)
    ap.add_argument('--endpoint', action='append', help='Custom endpoint spec name:path (can repeat)')
    return ap.parse_args()

def main():
    args = parse_args()
    base_url = args.base_url.rstrip('/')
    samples = args.samples
    concurrency = args.concurrency
    ingest_events = args.ingest_events
    ingest_batch = args.ingest_batch_size
    endpoints: List[Tuple[str,str]]
    if args.endpoint:
        endpoints = []
        for spec in args.endpoint:
            if ':' not in spec:
                print(f'[perf] invalid endpoint spec {spec}, expected name:/path')
                continue
            n, p = spec.split(':',1)
            endpoints.append((n, p if p.startswith('/') else '/' + p))
    else:
        endpoints = DEFAULT_ENDPOINTS
    results = {}
    for name, path in endpoints:
        all_lat = []
        threads = []
        def run_batch():
            all_lat.extend(time_endpoint(base_url, path, samples))
        for _ in range(concurrency):
            t = threading.Thread(target=run_batch)
            t.start(); threads.append(t)
        for t in threads: t.join()
        if all_lat:
            q = statistics.quantiles(all_lat, n=100)
            stats = {
                'count': len(all_lat),
                'p50_ms': q[49],
                'p90_ms': q[89],
                'p95_ms': q[94],
                'p99_ms': q[98],
                'mean_ms': statistics.mean(all_lat),
                'max_ms': max(all_lat)
            }
            results[name] = stats
    # Ingestion throughput test
    try:
        payloads = []
        now = int(time.time())
        for i in range(ingest_events):
            payloads.append({
                'event_id': f'perf_{now}_{i}',
                'tenant_id': 'perf',
                'message': 'throughput test event'
            })
        url = base_url + '/ingest'
        send_start = time.perf_counter()
        ingest_errors = 0
        for idx in range(0, len(payloads), ingest_batch):
            batch = payloads[idx:idx+ingest_batch]
            # Send individually to approximate real ingestion rather than a bulk endpoint
            for ev in batch:
                try:
                    r = requests.post(url, json=ev, timeout=5)
                    r.raise_for_status()
                except Exception:
                    ingest_errors += 1
        elapsed = time.perf_counter() - send_start
        eps = ingest_events / elapsed if elapsed > 0 else 0.0
        results['ingest_throughput'] = {
            'events': ingest_events,
            'elapsed_s': elapsed,
            'events_per_second': eps,
            'errors': ingest_errors,
            'error_rate': (ingest_errors / ingest_events) if ingest_events else 0.0
        }
    except Exception as e:
        results['ingest_throughput'] = {'error': str(e)}

    out = ART / f'perf_run_{int(time.time())}.json'
    out.write_text(json.dumps({'generated': datetime.datetime.utcnow().isoformat()+'Z', 'results': results}, indent=2))
    print(f'[perf] Wrote {out}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
