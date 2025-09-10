"""Push latest perf harness metrics to Prometheus Pushgateway if URL provided.
Usage:
  PERF_PUSHGATEWAY_URL=http://pushgateway:9091 python scripts/push_perf_metrics.py --job neuron-perf
"""
from __future__ import annotations
import os, json, pathlib, argparse, requests, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
PERF_DIR = ROOT / 'artifacts' / 'perf'

def latest_perf():
    if not PERF_DIR.exists():
        return None
    files = sorted(PERF_DIR.glob('perf_run_*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    return json.loads(files[0].read_text())

def format_metrics(data: dict, job: str) -> str:
    lines = []
    results = data.get('results', {})
    ts = int(time.time())
    for name, metrics in results.items():
        if 'p90_ms' in metrics:
            lines.append(f'neuron_perf_p90_ms{{endpoint="{name}"}} {metrics["p90_ms"]} {ts * 1000}')
        if 'p99_ms' in metrics:
            lines.append(f'neuron_perf_p99_ms{{endpoint="{name}"}} {metrics["p99_ms"]} {ts * 1000}')
        if name == 'ingest_throughput' and 'events_per_second' in metrics:
            lines.append(f'neuron_perf_ingest_events_per_second {metrics["events_per_second"]} {ts * 1000}')
    return '\n'.join(lines) + '\n'

def push(metrics: str, url: str, job: str):
    target = url.rstrip('/') + f'/metrics/job/{job}'
    r = requests.put(target, data=metrics.encode('utf-8'), timeout=10)
    if r.status_code >= 300:
        raise RuntimeError(f'Push failed {r.status_code} {r.text}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--job', default='neuron-perf')
    args = ap.parse_args()
    url = os.getenv('PERF_PUSHGATEWAY_URL')
    if not url:
        print('[push-perf] PERF_PUSHGATEWAY_URL not set, skip')
        return 0
    data = latest_perf()
    if not data:
        print('[push-perf] No perf data found')
        return 0
    metrics = format_metrics(data, args.job)
    push(metrics, url, args.job)
    print('[push-perf] Pushed metrics for job', args.job)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
