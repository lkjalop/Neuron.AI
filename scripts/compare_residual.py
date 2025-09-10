"""Residual contribution comparison utility.

Runs the neuromorphic benchmark twice: (1) residual disabled, (2) residual enabled,
then produces a Markdown diff summary focusing on:
  - uplift_ratio delta
  - noise false positive deltas (baseline & snn)
  - residual contribution mean gauge snapshot if available (queried from metrics endpoint optional)

Usage:
  python scripts/compare_residual.py --events 600 --patterns drift,burst,periodic_shift,noise --encoder rate_v2 --snn-mode proto \
      --out artifacts/perf/residual_compare.md

Notes:
- Assumes runtime parameters keys:
    seq.forecaster.enable (bool)
- Metrics endpoint optional; if unavailable, skips residual mean gauge read.
"""
from __future__ import annotations
import argparse, subprocess, json, os, sys, time, http.client, socket
from typing import Dict, Any

BENCH_SCRIPT = os.path.join(os.path.dirname(__file__), 'benchmark_neuromorphic.py')


def run_benchmark(args, enable_residual: bool) -> Dict[str, Any]:
    # Update param via runtime param script invocation: rely on benchmark to set other params
    # We inject an env var consumed by runtime_params if supported; fallback to param update inside script not available.
    # Simpler: call a small Python snippet to set param before running benchmark.
    toggle_code = (
        "from config import runtime_params; "
        f"runtime_params.update_param('seq.forecaster.enable', {str(enable_residual)}, reason='compare_residual');"
    )
    subprocess.run([sys.executable, '-c', toggle_code], check=False)
    cmd = [sys.executable, BENCH_SCRIPT,
           '--events', str(args.events),
           '--patterns', args.patterns,
           '--encoder', args.encoder,
           '--snn-mode', args.snn_mode]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    stdout = proc.stdout.strip()
    # Attempt to parse last JSON object printed (summary)
    parsed = None
    try:
        # Find last '{' and parse
        last_brace = stdout.rfind('{')
        if last_brace >= 0:
            snippet = stdout[last_brace:]
            parsed = json.loads(snippet)
    except Exception:
        parsed = {"error": "parse_failed", "raw": stdout[-500:]}
    if not parsed:
        parsed = {"error": "no_output", "raw": stdout[-500:]}
    parsed['residual_enabled'] = enable_residual
    return parsed


def fetch_residual_mean_metric(host: str = 'localhost', port: int = 8000, timeout: float = 0.3):
    # Optional: try to scrape metrics endpoint (Prometheus text format) to find neuron_snn_residual_contrib_mean
    try:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.request('GET', '/metrics')
        resp = conn.getresponse()
        if resp.status != 200:
            return None
        body = resp.read().decode('utf-8', errors='ignore')
        for line in body.splitlines():
            if line.startswith('neuron_snn_residual_contrib_mean'):
                # Format: metric{tenant="t0"} value
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        val = float(parts[-1])
                        return val
                    except Exception:
                        pass
        return None
    except (socket.timeout, ConnectionRefusedError, OSError):
        return None


def build_markdown(baseline: Dict[str, Any], residual: Dict[str, Any], residual_mean: float | None) -> str:
    def safe(v, key, default=0):
        return v.get(key, default)
    lines = ["# Residual Comparison", "", f"Events: {baseline.get('events')}", ""]
    lines.append("## Summary Table")
    lines.append("| Setting | UpliftRatio | BaselineAnoms | SNNAnoms | NoiseFP_Baseline | NoiseFP_SNN |")
    lines.append("|---------|-------------|---------------|---------|------------------|-------------|")
    for r in (baseline, residual):
        lines.append(
            f"| {'Residual ON' if r['residual_enabled'] else 'Residual OFF'} | "
            f"{safe(r, 'combinations', [{}])[0].get('aggregate_uplift_ratio', r.get('uplift_ratio','?'))} | "
            f"{safe(r, 'baseline_anomalies','?')} | {safe(r, 'snn_anomalies','?')} | "
            f"{safe(r, 'noise_false_positive_baseline','?')} | {safe(r, 'noise_false_positive_snn','?')} |")
    # Deltas
    try:
        uplift_base = baseline.get('uplift_ratio') or 0
        uplift_res = residual.get('uplift_ratio') or 0
        uplift_delta = uplift_res - uplift_base
    except Exception:
        uplift_delta = 'n/a'
    lines.append("\n## Deltas")
    lines.append(f"- Uplift Ratio Delta: {uplift_delta}")
    try:
        delta_fp_b = (residual.get('noise_false_positive_baseline', 0) - baseline.get('noise_false_positive_baseline', 0))
        delta_fp_s = (residual.get('noise_false_positive_snn', 0) - baseline.get('noise_false_positive_snn', 0))
        lines.append(f"- Noise False Positives Baseline Delta: {delta_fp_b}")
        lines.append(f"- Noise False Positives SNN Delta: {delta_fp_s}")
    except Exception:
        pass
    if residual_mean is not None:
        lines.append(f"- Residual Contribution Mean (current runtime): {residual_mean:.4f}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--events', type=int, default=600)
    ap.add_argument('--patterns', type=str, default='drift,burst,periodic_shift,noise')
    ap.add_argument('--snn-mode', type=str, default='proto')
    ap.add_argument('--encoder', type=str, default='rate_v2')
    ap.add_argument('--out', type=str, default='artifacts/perf/residual_compare.md')
    ap.add_argument('--metrics-host', type=str, default='localhost')
    ap.add_argument('--metrics-port', type=int, default=8000)
    args = ap.parse_args()

    baseline_result = run_benchmark(args, enable_residual=False)
    residual_result = run_benchmark(args, enable_residual=True)
    residual_mean = fetch_residual_mean_metric(args.metrics_host, args.metrics_port)

    md = build_markdown(baseline_result, residual_result, residual_mean)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        f.write(md)
    print(md)

if __name__ == '__main__':
    main()
