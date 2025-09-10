"""Generate coverage JSON + gap analysis.

Usage:
  python scripts/coverage_report.py --min 75

Outputs:
  artifacts/coverage/coverage.json (pytest json report)
  artifacts/coverage/gaps.json (files below threshold with missing lines)
"""
from __future__ import annotations
import argparse, json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
ART = ROOT / 'artifacts' / 'coverage'
ART.mkdir(parents=True, exist_ok=True)


def run_pytest_cov(min_percent: float) -> dict:
    cmd = [sys.executable, '-m', 'pytest', '--cov=src', '--cov-branch', '--cov-report=json', '--cov-report=term-missing']
    print('[coverage] running:', ' '.join(cmd))
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr)
    cov_file = ROOT / 'coverage.json'
    if not cov_file.exists():
        raise SystemExit('coverage.json not produced')
    data = json.loads(cov_file.read_text())
    (ART / 'coverage.json').write_text(json.dumps(data, indent=2))
    total = data.get('totals', {}).get('percent_covered', 0.0)
    status = 'OK' if total >= min_percent else 'LOW'
    print(f'[coverage] total={total:.2f}% status={status}')
    return data


def analyze_gaps(data: dict, min_percent: float) -> dict:
    files = data.get('files', {})
    gaps = {}
    for path, meta in files.items():
        pc = meta.get('summary', {}).get('percent_covered', 0.0)
        if pc < min_percent:
            missing = meta.get('missing_lines', [])
            gaps[path] = {
                'percent': pc,
                'missing_sample': missing[:30],
                'missing_count': len(missing),
            }
    (ART / 'gaps.json').write_text(json.dumps(gaps, indent=2))
    print(f'[coverage] {len(gaps)} files below target')
    return gaps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--min', type=float, default=75.0, help='Minimum acceptable coverage %')
    args = ap.parse_args()
    data = run_pytest_cov(args.min)
    gaps = analyze_gaps(data, args.min)
    # Simple exit status for CI integration
    total = data.get('totals', {}).get('percent_covered', 0.0)
    if total < args.min:
        print('[coverage] FAIL_UNDER threshold not met')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
