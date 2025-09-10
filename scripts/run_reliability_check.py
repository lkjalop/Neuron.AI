"""Reliability Check Script

Runs a deterministic synthetic stream multiple times to ensure anomaly rate
stays within expected stability bounds.

Extended (fusion stability):
If `RELIABILITY_ENABLE_FUSION=true` (or `ENABLE_FUSION=true`), fusion is
enabled for the orchestrator and we record anomaly counts for:
 - baseline_detectors: all non-fusion detectors combined
 - fused: synthetic fused anomalies (detector == fusion strategy name)

Two relative variance (std/mean) values are computed:
 - baseline_rel_var
 - fused_rel_var

Failure conditions (non-zero exit):
 1. baseline_rel_var > RELIABILITY_TOLERANCE
 2. fused_rel_var > RELIABILITY_TOLERANCE
 3. fused_rel_var > baseline_rel_var * RELIABILITY_FUSION_MULTIPLIER

Environment Variables:
 - RELIABILITY_RUNS (default 3)
 - RELIABILITY_COUNT (default 400)
 - RELIABILITY_TOLERANCE (default 0.15)
 - RELIABILITY_ENABLE_FUSION (default false)
 - RELIABILITY_FUSION_MULTIPLIER (default 1.5)
 - FUSION_STRATEGY (optional; default weighted_temporal)

Exit Codes:
 0 success
 1 variance failure (general)
 2 no anomalies produced in baseline
 3 fusion enabled but produced no fused anomalies (treated as instability)
"""
from __future__ import annotations

import statistics, sys, os

from detect.orchestrator import build_default_orchestrator
from ingest.adapters.synthetic import synthetic_stream

RUNS = int(os.getenv("RELIABILITY_RUNS", 3))
COUNT = int(os.getenv("RELIABILITY_COUNT", 400))
TOLERANCE = float(os.getenv("RELIABILITY_TOLERANCE", 0.15))  # relative std/mean
FUSION_ENABLED = os.getenv("RELIABILITY_ENABLE_FUSION", "false").lower() == "true" or os.getenv("ENABLE_FUSION", "false").lower() == "true"
FUSION_MULT = float(os.getenv("RELIABILITY_FUSION_MULTIPLIER", 1.5))
FUSION_STRATEGY = os.getenv("FUSION_STRATEGY", "weighted_temporal")

# If reliability explicitly wants fusion, set orchestrator flag before builds
if FUSION_ENABLED:
    os.environ["ENABLE_FUSION"] = "true"
    os.environ.setdefault("FUSION_STRATEGY", FUSION_STRATEGY)


def run_once():
    """Execute one deterministic pass returning (baseline_count, fused_count)."""
    orch = build_default_orchestrator()
    fusion_name = None
    if FUSION_ENABLED:
        # WeightedTemporalFusion.name = "weighted_temporal" (avoid hard coupling if others added)
        fusion_name = os.getenv("FUSION_STRATEGY", "weighted_temporal").lower()
    base_ct = 0
    fused_ct = 0
    for evt in synthetic_stream(count=COUNT, anomaly_period=111):
        anomalies = orch.process_event(evt)
        if not anomalies:
            continue
        for a in anomalies:
            if fusion_name and a.detector == fusion_name:
                fused_ct += 1
            else:
                base_ct += 1
    return base_ct, fused_ct


def _rel_var(vals: list[int]) -> float:
    m = statistics.mean(vals)
    if m == 0:
        return float("inf")  # Force failure upstream
    return statistics.pstdev(vals) / m


def main():
    base_counts: list[int] = []
    fused_counts: list[int] = []
    for _ in range(RUNS):
        b, f = run_once()
        base_counts.append(b)
        if FUSION_ENABLED:
            fused_counts.append(f)

    base_mean = statistics.mean(base_counts) if base_counts else 0
    if base_mean == 0:
        print("No anomalies produced by baseline detectors; failing reliability check")
        sys.exit(2)
    base_rel = _rel_var(base_counts)

    print(f"[reliability] baseline_counts={base_counts} mean={base_mean:.2f} rel_var={base_rel:.4f} tol={TOLERANCE}")
    if base_rel > TOLERANCE:
        print("Baseline variance exceeds tolerance")
        sys.exit(1)

    if FUSION_ENABLED:
        if not fused_counts:
            print("Fusion enabled but produced no fused anomalies; failing")
            sys.exit(3)
        fused_mean = statistics.mean(fused_counts)
        if fused_mean == 0:
            print("Fusion produced zero fused anomalies; failing")
            sys.exit(3)
        fused_rel = _rel_var(fused_counts)
        print(
            f"[reliability] fused_counts={fused_counts} mean={fused_mean:.2f} rel_var={fused_rel:.4f} tol={TOLERANCE} mult_limit={FUSION_MULT:.2f} baseline_rel={base_rel:.4f}"
        )
        if fused_rel > TOLERANCE:
            print("Fused variance exceeds tolerance")
            sys.exit(1)
        if fused_rel > base_rel * FUSION_MULT:
            print("Fused variance exceeds allowed multiplier over baseline")
            sys.exit(1)
    else:
        print("[reliability] Fusion not enabled; fused variance check skipped")

    print("Reliability check passed")


if __name__ == "__main__":
    main()
