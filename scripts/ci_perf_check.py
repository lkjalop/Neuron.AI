"""CI performance check with baseline comparison.

Runs perf harness, enforces absolute thresholds AND optional delta thresholds against stored baseline.

Env Overrides:
    PERF_P90_MAX_MS (default 400)
    PERF_P95_MAX_MS (default 600)
    PERF_P99_MAX_MS (default 900)
    PERF_P90_DELTA_MAX_PCT (default 25)   # Max allowed p90 increase percentage vs baseline
    PERF_P95_DELTA_MAX_PCT (default 25)   # Max allowed p95 increase percentage vs baseline
    PERF_P99_DELTA_MAX_PCT (default 25)   # Max allowed p99 increase percentage vs baseline
    PERF_INGEST_ERROR_RATE_MAX (default 0.02)  # 2%
    PERF_BASELINE_UPDATE (set to '1' to write new baseline after success)

Baseline file: artifacts/perf/baseline.json
"""
from __future__ import annotations
import os, subprocess, time, json, pathlib, sys, signal

ROOT = pathlib.Path(__file__).resolve().parents[1]
HARNESS = ROOT / 'scripts' / 'perf_harness.py'

P90_MAX = float(os.getenv('PERF_P90_MAX_MS', '400'))
P95_MAX = float(os.getenv('PERF_P95_MAX_MS', '600'))
P99_MAX = float(os.getenv('PERF_P99_MAX_MS', '900'))
P90_DELTA_MAX = float(os.getenv('PERF_P90_DELTA_MAX_PCT', '25'))
P95_DELTA_MAX = float(os.getenv('PERF_P95_DELTA_MAX_PCT', '25'))
P99_DELTA_MAX = float(os.getenv('PERF_P99_DELTA_MAX_PCT', '25'))
INGEST_ERR_RATE_MAX = float(os.getenv('PERF_INGEST_ERROR_RATE_MAX', '0.02'))
BASELINE_UPDATE = os.getenv('PERF_BASELINE_UPDATE') == '1'
BASELINE_PATH = ROOT / 'artifacts' / 'perf' / 'baseline.json'


def start_server():
    return subprocess.Popen([sys.executable, '-m', 'uvicorn', 'core.main:app', '--factory', '--port', '8000'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def wait_ready(timeout=30):
    import urllib.request
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2) as r:  # type: ignore
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def parse_latest_perf() -> dict:
    perf_dir = ROOT / 'artifacts' / 'perf'
    if not perf_dir.exists():
        return {}
    files = sorted(perf_dir.glob('perf_run_*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return {}
    return json.loads(files[0].read_text())


def main():
    if not HARNESS.exists():
        print('[ci-perf] Harness missing, skip (treat as pass)')
        return 0
    srv = start_server()
    try:
        if not wait_ready():
            print('[ci-perf] Server not ready in time')
            return 1
        # Reduce samples for CI speed by setting env perhaps; current harness uses constants
        # (Future: add args to harness for sample count / concurrency)
        rc = subprocess.call([sys.executable, str(HARNESS)])
        if rc != 0:
            print('[ci-perf] Harness failed')
            return rc
        data = parse_latest_perf()
        if not data:
            print('[ci-perf] No perf output found')
            return 1
        results = data.get('results', {})
        violations = []
        # Load baseline if present
        baseline = {}
        if BASELINE_PATH.exists():
            try:
                baseline = json.loads(BASELINE_PATH.read_text())
            except Exception:
                print('[ci-perf] Warning: baseline unreadable')
        for name, metrics in results.items():
            p90 = metrics.get('p90_ms')
            p95 = metrics.get('p95_ms')
            p99 = metrics.get('p99_ms')
            if p90 is not None and p90 > P90_MAX:
                violations.append(f'{name} p90 {p90:.1f}ms > {P90_MAX}ms')
            if p95 is not None and p95 > P95_MAX:
                violations.append(f'{name} p95 {p95:.1f}ms > {P95_MAX}ms')
            if p99 is not None and p99 > P99_MAX:
                violations.append(f'{name} p99 {p99:.1f}ms > {P99_MAX}ms')
            # Delta checks
            if baseline.get(name):
                bp90 = baseline[name].get('p90_ms')
                bp95 = baseline[name].get('p95_ms')
                bp99 = baseline[name].get('p99_ms')
                if bp90 and p90 and bp90 > 0:
                    inc = ((p90 - bp90) / bp90) * 100.0
                    if inc > P90_DELTA_MAX:
                        violations.append(f'{name} p90 regression +{inc:.1f}% > {P90_DELTA_MAX}% (baseline {bp90:.1f}ms -> {p90:.1f}ms)')
                if bp95 and p95 and bp95 > 0:
                    inc = ((p95 - bp95) / bp95) * 100.0
                    if inc > P95_DELTA_MAX:
                        violations.append(f'{name} p95 regression +{inc:.1f}% > {P95_DELTA_MAX}% (baseline {bp95:.1f}ms -> {p95:.1f}ms)')
                if bp99 and p99 and bp99 > 0:
                    inc = ((p99 - bp99) / bp99) * 100.0
                    if inc > P99_DELTA_MAX:
                        violations.append(f'{name} p99 regression +{inc:.1f}% > {P99_DELTA_MAX}% (baseline {bp99:.1f}ms -> {p99:.1f}ms)')
        # Ingestion error gating
        ingest = results.get('ingest_throughput')
        if ingest and 'error_rate' in ingest:
            if ingest['error_rate'] > INGEST_ERR_RATE_MAX:
                violations.append(f'ingest_throughput error_rate {ingest["error_rate"]:.3f} > {INGEST_ERR_RATE_MAX:.3f}')
        if violations:
            print('[ci-perf] PERF REGRESSIONS:')
            for v in violations:
                print('  -', v)
            return 1
        print('[ci-perf] Performance within thresholds & delta limits')
        if BASELINE_UPDATE or not BASELINE_PATH.exists():
            BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
            # Keep only latency endpoints (ignore ingest throughput for baseline now)
            slim = {k: {m: results[k][m] for m in ('p90_ms','p95_ms','p99_ms') if m in results[k]} for k in results if 'p90_ms' in results[k]}
            BASELINE_PATH.write_text(json.dumps(slim, indent=2))
            print(f'[ci-perf] Baseline written/updated at {BASELINE_PATH}')
        return 0
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=5)
        except subprocess.TimeoutExpired:
            srv.kill()

if __name__ == '__main__':
    raise SystemExit(main())
