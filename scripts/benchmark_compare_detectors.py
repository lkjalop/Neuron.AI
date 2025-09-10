"""Compare detector configurations.

Runs multiple orchestrator configurations sequentially on the same synthetic
event stream and reports anomaly counts & per-detector contribution.

Configurations:
 - baseline
 - baseline+iforest (if EXPERIMENTAL_ISOFOREST=true for run)
 - baseline+iforest+snn (if ENABLE_SNN=true)

Outputs JSON artifact under artifacts/perf/benchmark_compare_<timestamp>.json
"""
from __future__ import annotations
import argparse, os, json, time, copy
from typing import List, Dict

from core.event import Event
from detect.orchestrator import build_default_orchestrator, Anomaly


def generate_events(n: int, tenant: str) -> List[Event]:
    import random
    events: List[Event] = []
    base = 10.0
    for i in range(n):
        sev = base + random.uniform(-1.5, 1.5)
        if i % 70 == 0 and i > 0:
            sev += random.uniform(15, 20)
        features = {"f0": sev, "f1": sev * 0.3}
        events.append(Event.create(event_type="bench", severity=sev, tenant_id=tenant, features=features))
    return events


def run_config(events: List[Event]) -> Dict:
    orch = build_default_orchestrator()
    anomalies: List[Anomaly] = []
    for ev in events:
        anomalies.extend(orch.process_event(ev))
    det_counts: Dict[str, int] = {}
    for a in anomalies:
        det_counts[a.detector] = det_counts.get(a.detector, 0) + 1
    total = len(anomalies)
    return {
        "total_anomalies": total,
        "detector_counts": det_counts,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", type=int, default=400)
    ap.add_argument("--tenant", type=str, default="bench")
    ap.add_argument("--out-dir", default="artifacts/perf")
    args = ap.parse_args()
    events = generate_events(args.events, args.tenant)
    base_env = dict(os.environ)
    results = {}

    # baseline only (ensure flags off)
    for k in ["EXPERIMENTAL_ISOFOREST", "ENABLE_SNN"]:
        base_env.pop(k, None)
    os.environ.clear(); os.environ.update(base_env)
    results['baseline'] = run_config(events)

    # baseline + iforest
    env_iforest = copy.deepcopy(base_env)
    env_iforest["EXPERIMENTAL_ISOFOREST"] = "true"
    os.environ.clear(); os.environ.update(env_iforest)
    results['baseline_iforest'] = run_config(events)

    # baseline + iforest + snn
    env_snn = copy.deepcopy(env_iforest)
    env_snn["ENABLE_SNN"] = "true"
    os.environ.clear(); os.environ.update(env_snn)
    results['baseline_iforest_snn'] = run_config(events)

    out_dir = args.out_dir
    import pathlib
    p = pathlib.Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    out_path = p / f"benchmark_compare_{ts}.json"
    out_path.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(f"Benchmark results: {out_path}")
    for name, data in results.items():
        print(f"{name}: total={data['total_anomalies']} counts={data['detector_counts']}")


if __name__ == "__main__":
    main()
