"""Generate a markdown comment summarizing perf delta vs baseline.

Inputs:
  artifacts/perf/latest.json (current run metrics)
  artifacts/perf/baseline.json (existing baseline)

Output:
  stdout markdown block (can be piped to gh pr comment) and artifacts/perf/perf_pr_comment.md

Sample Usage:
  python scripts/perf_pr_comment.py > perf_comment.md
  gh pr comment <PRNUM> --body-file perf_comment.md
"""
from __future__ import annotations
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PERF = ROOT / 'artifacts' / 'perf'

FIELDS = [
    ('p50_ms','Median (p50)'),
    ('p90_ms','p90'),
    ('p95_ms','p95'),
    ('p99_ms','p99'),
    ('throughput_eps','Throughput (events/s)'),
    ('ingestion_error_rate','Ingest Error Rate'),
]

def load_json(path: pathlib.Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

def fmt_delta(curr, base):
    if base in (None, 0):
        return 'n/a'
    try:
        delta = (curr - base) / base * 100.0
        sign = '+' if delta >= 0 else ''
        return f"{sign}{delta:.1f}%"
    except Exception:
        return 'n/a'


def main():
    latest = load_json(PERF / 'latest.json')
    baseline = load_json(PERF / 'baseline.json')
    lines = ["### Performance Delta", "", "| Metric | Current | Baseline | Delta |", "|--------|---------|----------|-------|"]
    for key, label in FIELDS:
        cur = latest.get(key)
        base = baseline.get(key)
        if cur is None and key == 'ingestion_error_rate':  # backward compat
            cur = latest.get('ingestion_errors')
        delta = fmt_delta(cur, base)
        def _fmt(v):
            if isinstance(v, (int,float)):
                return f"{v:.2f}" if 'rate' in key or 'throughput' in key else f"{v:.1f}"
            return '—'
        lines.append(f"| {label} | {_fmt(cur)} | {_fmt(base)} | {delta} |")
    # Pass/fail quick summary (use p95 & error rate heuristics)
    p95_cur = latest.get('p95_ms')
    p95_base = baseline.get('p95_ms')
    err_rate = latest.get('ingestion_error_rate', 0.0)
    status_msgs = []
    if p95_cur and p95_base:
        if p95_cur <= p95_base * 1.1:
            status_msgs.append('p95 OK')
        else:
            status_msgs.append('p95 regression')
    if err_rate and err_rate > 0.01:
        status_msgs.append('high ingest error rate')
    if not status_msgs:
        status_msgs.append('baseline stable')
    lines.append("")
    lines.append("Status: " + ', '.join(status_msgs))
    out_md = '\n'.join(lines) + '\n'
    (PERF / 'perf_pr_comment.md').write_text(out_md)
    sys.stdout.write(out_md)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
