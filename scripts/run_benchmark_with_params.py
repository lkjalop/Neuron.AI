#!/usr/bin/env python
"""Helper to set runtime params programmatically before running neuromorphic benchmark.
Usage (PowerShell):
  $env:PYTHONPATH='src'; python scripts/run_benchmark_with_params.py \
      --rate-scale 3.0 --shrink 0.5 --min-floor 0.04 --debug \
      --events 400 --patterns drift,burst,periodic --mode all --encoder rate_v2
"""
from __future__ import annotations
import argparse, json, sys
from config import runtime_params
import importlib.util, pathlib, types

# Lazy local import of benchmark_neuromorphic without package-level import errors
_bench_path = pathlib.Path(__file__).parent / 'benchmark_neuromorphic.py'
spec = importlib.util.spec_from_file_location('benchmark_neuromorphic', _bench_path)
bench = importlib.util.module_from_spec(spec)  # type: ignore
assert spec and spec.loader
spec.loader.exec_module(bench)  # type: ignore

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rate-scale', type=float, default=None)
    ap.add_argument('--shrink', type=float, default=None)
    ap.add_argument('--min-floor', type=float, default=None)
    ap.add_argument('--debug', action='store_true')
    ap.add_argument('--no-cap', action='store_true')
    ap.add_argument('--events', type=int, default=400)
    ap.add_argument('--patterns', type=str, default='drift,burst,periodic')
    ap.add_argument('--mode', type=str, default='all', help='proto|lif|all')
    ap.add_argument('--encoder', type=str, default='rate_v2')
    ap.add_argument('--out', type=str, default=None)
    ap.add_argument('--markdown', type=str, default=None)
    args = ap.parse_args()

    if args.rate_scale is not None:
        runtime_params.update_param('snn.rate_scale', args.rate_scale, reason='benchmark_override')
    if args.shrink is not None:
        runtime_params.update_param('snn.encoder.rate_v2.global_shrink', args.shrink, reason='benchmark_override')
    if args.min_floor is not None:
        runtime_params.update_param('snn.encoder.rate_v2.min_floor', args.min_floor, reason='benchmark_override')
    if args.debug:
        runtime_params.update_param('snn.encoder.rate_v2.debug', True, reason='benchmark_override')
    if args.no_cap:
        runtime_params.update_param('snn.encoder.rate_v2.debug_no_cap', True, reason='benchmark_override')
    runtime_params.update_param('snn.encoder', args.encoder, reason='benchmark_override')

    patterns = args.patterns.split(',') if args.patterns else []

    result = bench.run_benchmark(
        events=args.events,
        patterns=patterns,
        snn_modes=['proto','lif'] if args.mode=='all' else [args.mode],
        encoder=args.encoder,
    )

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
    if args.markdown:
        bench.write_markdown(result, args.markdown)

    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
