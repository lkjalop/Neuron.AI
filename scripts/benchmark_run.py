"""Unified Benchmark Runner

Executes multiple configurations (env-flag based) and captures anomaly counts
and latency aggregates for quick comparative snapshots.
"""
from __future__ import annotations

import os, time, json
from statistics import mean

from detect.orchestrator import build_default_orchestrator
from ingest.adapters.synthetic import synthetic_stream

CONFIGS = [
    {"ENABLE_ISO": "false", "ENABLE_SNN": "false"},
    {"ENABLE_ISO": "true", "ENABLE_SNN": "false"},
    {"ENABLE_ISO": "false", "ENABLE_SNN": "true"},
]
COUNT = int(os.getenv("BENCHMARK_COUNT", 600))


def run_config(env: dict[str,str]):
    # Patch environment for this run
    backup = {}
    for k,v in env.items():
        backup[k] = os.environ.get(k)
        os.environ[k] = v
    try:
        orch = build_default_orchestrator()
        anomalies = 0
        start = time.perf_counter()
        for evt in synthetic_stream(count=COUNT, anomaly_period=111):
            anomalies += len(orch.process_event(evt))
        dur = time.perf_counter() - start
        return {"anomalies": anomalies, "duration_s": dur}
    finally:
        for k,v in backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def main():
    results = []
    for cfg in CONFIGS:
        res = run_config(cfg)
        res.update(cfg)
        results.append(res)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
