"""Run a short profiling session against key endpoints & ingestion.
Outputs:
 - artifacts/perf/profile_<ts>.pstats (raw cProfile)
 - artifacts/perf/profile_<ts>.json (top functions summary)

Usage:
  python scripts/profile_run.py --duration 5 --base-url http://127.0.0.1:8000
"""
from __future__ import annotations
import argparse, cProfile, pstats, io, time, json, pathlib, requests, threading

ROOT = pathlib.Path(__file__).resolve().parents[1]
ART = ROOT / 'artifacts' / 'perf'
ART.mkdir(parents=True, exist_ok=True)

TARGET_ENDPOINTS = ['/diagnostics/config', '/governance/recommendations/recent']


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-url', default='http://127.0.0.1:8000')
    ap.add_argument('--duration', type=int, default=5, help='Seconds for load phase')
    ap.add_argument('--concurrency', type=int, default=4)
    return ap.parse_args()


def load_worker(stop_event, base_url: str):
    i = 0
    while not stop_event.is_set():
        path = TARGET_ENDPOINTS[i % len(TARGET_ENDPOINTS)]
        url = base_url.rstrip('/') + path
        try:
            r = requests.get(url, timeout=3)
            r.raise_for_status()
        except Exception:
            pass
        i += 1


def profile_session(args):
    pr = cProfile.Profile()
    stop_event = threading.Event()
    threads = [threading.Thread(target=load_worker, args=(stop_event, args.base_url)) for _ in range(args.concurrency)]
    for t in threads: t.start()
    pr.enable()
    # Simple ingestion loop to mix workloads
    ingest_url = args.base_url.rstrip('/') + '/ingest'
    start = time.time()
    n_ingest = 0
    while time.time() - start < args.duration:
        ev = { 'event_id': f'prof_{n_ingest}', 'tenant_id': 'prof', 'message': 'profiling event'}
        try:
            requests.post(ingest_url, json=ev, timeout=2)
        except Exception:
            pass
        n_ingest += 1
    pr.disable()
    stop_event.set()
    for t in threads: t.join()
    ts = int(time.time())
    raw_path = ART / f'profile_{ts}.pstats'
    pr.dump_stats(str(raw_path))
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(40)
    # Parse top lines crudely
    lines = [l for l in s.getvalue().splitlines() if l.strip()]
    summary = {'generated': ts, 'top': lines[:60], 'ingested_events': n_ingest}
    (ART / f'profile_{ts}.json').write_text(json.dumps(summary, indent=2))
    print(f'[profile] wrote {raw_path}')
    return 0

if __name__ == '__main__':
    args = parse_args()
    raise SystemExit(profile_session(args))
