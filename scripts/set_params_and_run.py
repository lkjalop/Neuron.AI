"""Helper script to set runtime params then invoke neuromorphic benchmark.

This avoids complex PowerShell inline quoting when sweeping parameters.

Usage examples (from repo root):
  python scripts/set_params_and_run.py --rate-scale 1.0 --shrink 0.1 --floor 0.05 --events 300
  python scripts/set_params_and_run.py --rate-scale 2.0 --shrink 0.1 --floor 0.05 --events 300
  python scripts/set_params_and_run.py --rate-scale 3.0 --shrink 0.08 --floor 0.05 --events 300 --debug
"""
from __future__ import annotations
import argparse, sys
from config import runtime_params  # type: ignore
import importlib.util, pathlib, types

# Dynamically load benchmark_neuromorphic to avoid package import ambiguity when scripts not a package
_bench_path = pathlib.Path(__file__).parent / 'benchmark_neuromorphic.py'
spec = importlib.util.spec_from_file_location('benchmark_neuromorphic', _bench_path)
if spec and spec.loader:  # type: ignore[truthy-function]
  benchmark_neuromorphic = importlib.util.module_from_spec(spec)  # type: ignore
  sys.modules['benchmark_neuromorphic'] = benchmark_neuromorphic  # type: ignore
  spec.loader.exec_module(benchmark_neuromorphic)  # type: ignore
else:  # pragma: no cover
  raise ImportError('Could not load benchmark_neuromorphic module')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rate-scale', type=float, default=1.0)
    ap.add_argument('--shrink', type=float, default=0.1)
    ap.add_argument('--floor', type=float, default=0.04)
    ap.add_argument('--events', type=int, default=300)
    ap.add_argument('--patterns', type=str, default='drift,burst,periodic')
    ap.add_argument('--mode', type=str, default='proto', choices=['proto','lif'])
    ap.add_argument('--encoder', type=str, default='rate_v2', choices=['rate_v1','rate_v2'])
    ap.add_argument('--debug', action='store_true')
    ap.add_argument('--no-cap', action='store_true', help='Disable density cap in debug')
    args = ap.parse_args()

    # Apply params with audit reasons
    runtime_params.update_param('detection.enable_snn', True, reason='set_params_run_enable')
    runtime_params.update_param('snn.mode', args.mode, reason='set_params_run_mode')
    runtime_params.update_param('snn.encoder', args.encoder, reason='set_params_run_encoder')
    runtime_params.update_param('snn.rate_scale', args.rate_scale, reason='set_params_run_rate_scale')
    runtime_params.update_param('snn.encoder.rate_v2.global_shrink', args.shrink, reason='set_params_run_shrink')
    runtime_params.update_param('snn.encoder.rate_v2.min_floor', args.floor, reason='set_params_run_floor')
    runtime_params.update_param('snn.encoder.rate_v2.debug', bool(args.debug), reason='set_params_run_debug')
    runtime_params.update_param('snn.encoder.rate_v2.debug_no_cap', bool(args.no_cap), reason='set_params_run_debug_no_cap')

    print(f"[set_params_and_run] params applied: rate_scale={args.rate_scale} shrink={args.shrink} floor={args.floor} debug={args.debug} no_cap={args.no_cap}")

    # Delegate to benchmark runner (single combination)
    pats = [p.strip() for p in args.patterns.split(',') if p.strip()]
    result = benchmark_neuromorphic.run_benchmark(args.events, pats, args.mode, args.encoder)
    print('[set_params_and_run] benchmark result:')
    import json
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    sys.exit(main())
