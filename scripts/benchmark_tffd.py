"""Time-To-First-Detection (TTFD) benchmark harness.

Generates synthetic event patterns and measures the elapsed wall clock time
and event index until the first anomaly is produced by baseline and (if
enabled) SNN / temporal detectors.

Usage (powershell):
  python scripts/benchmark_tffd.py --patterns periodic_shift --events 200

Patterns:
  periodic_shift  - abrupt amplitude increase after warmup
  slow_ramp       - gradual linear increase across window
  beacon_interval - repeating spike every N events
"""
from __future__ import annotations

import argparse, time, statistics
from core.pipeline import Pipeline
from core.event import Event
from config import runtime_params
from core.detect.interface import registry


def gen_periodic_shift(n: int):
    for i in range(n):
        if i < n // 2:
            yield {"cpu": 1.0, "mem": 1.2}
        else:
            yield {"cpu": 10.0 + (i % 3), "mem": 12.0 + (i % 5)}


def gen_slow_ramp(n: int):
    for i in range(n):
        yield {"cpu": 1.0 + 0.05 * i, "mem": 1.0 + 0.04 * i}


def gen_beacon_interval(n: int, interval: int = 15):
    for i in range(n):
        spike = (i % interval) == 0
        yield {"cpu": 8.0 if spike else 1.0, "mem": 1.5 if spike else 1.0}


PATTERNS = {
    "periodic_shift": gen_periodic_shift,
    "slow_ramp": gen_slow_ramp,
    "beacon_interval": gen_beacon_interval,
}


def run_pattern(name: str, events: int, tenant: str) -> dict:
    gen = PATTERNS[name]
    p = Pipeline([tenant])
    t0 = time.perf_counter()
    first_detection_idx = {}
    for idx, feats in enumerate(gen(events)):
        ev = Event(tenant_id=tenant, features=feats)
        p.ingestion.queue.put_nowait(ev)  # type: ignore
        # process synchronously to keep timing simple
    import asyncio
    asyncio.run(p.flush())
    # Inspect detectors (baseline + optional snn + temporal stub) via trace store or registry
    # For now, approximate by scanning precision proxy & fusion counters not exposed directly.
    # Simpler: re-run detectors sequentially to locate earliest anomaly index.
    baseline = registry.get('baseline')
    snn = registry.get('snn')
    temporal = registry.get('temporal')
    # Re-simulate to find earliest anomaly indices
    idx = 0
    for feats in gen(events):
        ev = Event(tenant_id=tenant, features=feats)
        if baseline and 'baseline' not in first_detection_idx:
            if baseline.process(ev):
                first_detection_idx['baseline'] = idx
        if snn and 'snn' not in first_detection_idx:
            if snn.process(ev):
                first_detection_idx['snn'] = idx
        if temporal and 'temporal' not in first_detection_idx:
            if temporal.process(ev):
                first_detection_idx['temporal'] = idx
        idx += 1
        if set(first_detection_idx.keys()) == {k for k in ['baseline', 'snn', 'temporal'] if registry.get(k)}:
            break
    elapsed = time.perf_counter() - t0
    return {"pattern": name, "elapsed_s": elapsed, "first_idx": first_detection_idx}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--patterns', nargs='+', default=['periodic_shift'])
    ap.add_argument('--events', type=int, default=200)
    ap.add_argument('--enable-snn', action='store_true')
    ap.add_argument('--enable-temporal', action='store_true')
    args = ap.parse_args()
    if args.enable_snn:
        runtime_params.update_param('detection.enable_snn', True, reason='ttfd_bench')
    if args.enable_temporal:
        runtime_params.update_param('detection.temporal.enable_transformer', True, reason='ttfd_bench')
    results = []
    for pat in args.patterns:
        if pat not in PATTERNS:
            print(f"Unknown pattern {pat}")
            continue
        out = run_pattern(pat, args.events, tenant='bench')
        results.append(out)
    for r in results:
        print(r)


if __name__ == '__main__':  # pragma: no cover
    main()
