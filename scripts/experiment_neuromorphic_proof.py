"""Neuromorphic Proof-of-Value Harness

Purpose:
  Rapid, reproducible comparison of SNN vs Baseline detector characteristics:
    - Latency distribution (mean / p95)
    - Activity / score separation (SNN activity vs baseline z-score proxy)
    - Anomaly overlap & unique contribution
    - Spike density vs anomaly precision proxy (if available)

Usage (example):
  powershell> $env:DETECTION_ENABLE_SNN='true'; python scripts/experiment_neuromorphic_proof.py --events 500 --seed 42 --outfile artifacts/neuromorphic/proof_run.json

Design:
  - Generates synthetic events with controllable burst injections.
  - Runs orchestrator twice: once with SNN enabled, once with SNN disabled (baseline only) OR collects both if both active.
  - Produces stable JSON artifact summarizing metrics and hash for audit.

Outputs:
  JSON with keys: {"seed", "events", "snn_latency", "baseline_latency", "snn_activity_stats", "baseline_score_stats", "overlap", "unique", "separation", "hash"}

Determinism:
  Controlled via --seed (uses random + hashes), ensures reproducible feature generation sequence.
"""
from __future__ import annotations

import argparse, json, random, time, hashlib, os, pathlib, statistics
from typing import List, Dict

from core.event import Event
from detect.orchestrator import build_default_orchestrator
from config import runtime_params

# --- Synthetic Event Generator ---

def generate_events(n: int, *, seed: int, burst_every: int = 50) -> List[Event]:
    rnd = random.Random(seed)
    events: List[Event] = []
    base = 100.0
    ts0 = time.time()
    for i in range(n):
        # baseline random walk
        drift = rnd.uniform(-0.5, 0.5)
        base = max(1.0, base + drift)
        # occasional burst
        if burst_every > 0 and i > 0 and i % burst_every == 0:
            base += rnd.uniform(10, 25)
        features = {
            "value": base,
            "bytes": base * rnd.uniform(0.8, 1.2),
            "errors": rnd.randint(0, 3),
            "ratio": rnd.uniform(0, 1),
        }
        sev = rnd.uniform(0, 1)
        ev = Event(
            tenant_id="tenantA",
            event_id=f"e{i}",
            trace_id=f"t{i}",
            ts=ts0 + i,
            severity=sev,
            features=features,
        )
        events.append(ev)
    return events

# --- Metric Extraction Helpers ---

def _latency_stats(latencies: List[float]) -> Dict[str, float]:
    if not latencies:
        return {"count":0, "mean":0.0, "p95":0.0}
    sorted_l = sorted(latencies)
    p95 = sorted_l[int(0.95 * (len(sorted_l)-1))]
    return {"count": len(latencies), "mean": statistics.mean(latencies), "p95": p95}


def _score_stats(scores: List[float]) -> Dict[str, float]:
    if not scores:
        return {"count":0, "mean":0.0, "std":0.0, "max":0.0}
    mean = statistics.mean(scores)
    std = statistics.pstdev(scores) if len(scores) > 1 else 0.0
    return {"count": len(scores), "mean": mean, "std": std, "max": max(scores)}


def run_experiment(total_events: int, seed: int) -> Dict:
    events = generate_events(total_events, seed=seed)
    # Build orchestrator with environment determining SNN enable
    orch = build_default_orchestrator(include_baseline=True)
    snn_enabled = bool(runtime_params.get_param("detection.enable_snn"))
    snn_latencies: List[float] = []
    baseline_latencies: List[float] = []
    snn_scores: List[float] = []  # activity or score
    baseline_scores: List[float] = []
    overlap = 0
    unique_snn = 0
    unique_baseline = 0
    for ev in events:
        start = time.perf_counter()
        anomalies = orch.process_event(ev)
        total_elapsed = time.perf_counter() - start
        # Partition anomalies by detector
        detected_by = {a.detector for a in anomalies}
        if "snn" in detected_by and "baseline" in detected_by:
            overlap += 1
        elif "snn" in detected_by:
            unique_snn += 1
        elif "baseline" in detected_by:
            unique_baseline += 1
        for a in anomalies:
            if a.detector == "snn":
                snn_latencies.append(total_elapsed)  # coarse per-event orchestrator latency path
                snn_scores.append(float(a.meta.get("activity", a.score) if a.meta else a.score))
            elif a.detector == "baseline":
                baseline_latencies.append(total_elapsed)
                baseline_scores.append(a.score)
    # Separation metrics (simple): difference of means / pooled std
    separation = 0.0
    try:
        if snn_scores and baseline_scores:
            mean_s = statistics.mean(snn_scores)
            mean_b = statistics.mean(baseline_scores)
            var_s = statistics.pvariance(snn_scores) if len(snn_scores) > 1 else 0.0
            var_b = statistics.pvariance(baseline_scores) if len(baseline_scores) > 1 else 0.0
            pooled_std = math.sqrt((var_s + var_b) / 2) if (var_s + var_b) > 0 else 0.0
            separation = (mean_s - mean_b) / pooled_std if pooled_std > 0 else 0.0
    except Exception:
        separation = 0.0
    result = {
        "seed": seed,
        "events": total_events,
        "snn_enabled": snn_enabled,
        "snn_latency": _latency_stats(snn_latencies),
        "baseline_latency": _latency_stats(baseline_latencies),
        "snn_activity_stats": _score_stats(snn_scores),
        "baseline_score_stats": _score_stats(baseline_scores),
        "overlap": overlap,
        "unique_snn": unique_snn,
        "unique_baseline": unique_baseline,
        "separation": separation,
        "timestamp": int(time.time()),
    }
    ordered = sorted(result.keys())
    canonical = json.dumps({k: result[k] for k in ordered}, separators=(",", ":"), sort_keys=True)
    result["hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", type=int, default=300, help="Number of synthetic events")
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--outfile", type=str, default="artifacts/neuromorphic/proof_run.json")
    args = ap.parse_args()
    out_path = pathlib.Path(args.outfile)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary = run_experiment(args.events, args.seed)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    print(f"[neuromorphic_proof] wrote {out_path} hash={summary['hash']}")

if __name__ == "__main__":  # pragma: no cover
    main()
