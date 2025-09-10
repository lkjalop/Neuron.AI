"""Evaluate Baseline vs SNN detectors on a labeled synthetic events JSONL.

Outputs (default: artifacts/eval/):
  - snn_metrics.json                (raw SNN metrics only)
  - baseline_vs_snn_eval.json       (combined comparison + decision)

Decision logic aligns with docs/UPLIFT_TARGETS.md (do not silently diverge).

Usage:
  python scripts/generate_synthetic_events.py --count 800 --seed 42 > events.jsonl
  python scripts/evaluate_snn.py events.jsonl --baseline-window 50 --baseline-std 2.0 --snn-threshold 1.0

Labeled anomaly expectation: each event may contain labels.is_anomaly=true.
"""
from __future__ import annotations

import argparse, json, time, statistics, os, sys
from pathlib import Path
from typing import Dict, Any, Generator

try:
    from core.detect.baseline import BaselineDetector  # type: ignore
    from core.detect.snn import SNNDetector  # type: ignore
    from core.event import dict_to_event, validate_event, Event  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - path fallback
    import pathlib, sys as _sys
    ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"
    if str(ROOT) not in _sys.path:
        _sys.path.insert(0, str(ROOT))
    from core.detect.baseline import BaselineDetector  # type: ignore
    from core.detect.snn import SNNDetector  # type: ignore
    from core.event import dict_to_event, validate_event, Event  # type: ignore

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None  # type: ignore


def load_events(path: Path) -> Generator[Event, None, None]:
    """Stream Events from a JSONL file with resilient decoding.

    Handles UTF-8 BOM and ignores undecodable bytes instead of aborting.
    """
    with path.open("rb") as f:  # binary for manual decode
        for idx, raw_line in enumerate(f, 1):
            try:
                line = raw_line.decode("utf-8-sig", errors="ignore").strip()
            except Exception:  # pragma: no cover
                line = raw_line.decode("latin-1", errors="ignore").strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as je:
                print(f"WARN: bad JSON line {idx}: {je}", file=sys.stderr)
                continue
            try:
                ev = dict_to_event(raw)
                validate_event(ev)
                yield ev
            except Exception as e:  # noqa: BLE001
                print(f"WARN: bad event line {idx}: {e}", file=sys.stderr)
                continue


def compute_pr_metrics(tp: int, fp: int, fn: int) -> Dict[str, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def percentile(values, p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    d = k - f
    return s[f] + (s[c] - s[f]) * d


def decide(uplifts: Dict[str, float], overhead: Dict[str, float]) -> str:
    # Mirrors docs/UPLIFT_TARGETS.md (keep synced)
    recall_uplift = uplifts.get("recall_uplift", 0.0)
    precision_loss = uplifts.get("precision_loss", 0.0)
    added_p95 = overhead.get("added_latency_p95_ms", 0.0)
    if recall_uplift >= 0.15 and precision_loss <= 0.05 and added_p95 < 5.0:
        return "proceed"
    if recall_uplift < 0.05 or precision_loss > 0.08 or added_p95 > 8.0:
        return "retire_or_rethink"
    return "tune"


def main():
    ap = argparse.ArgumentParser(description="Baseline vs SNN evaluation harness")
    ap.add_argument("path", type=Path, help="Input JSONL events with labels")
    ap.add_argument("--baseline-window", type=int, default=50)
    ap.add_argument("--baseline-std", type=float, default=2.0)
    ap.add_argument("--snn-threshold", type=float, default=1.0)
    ap.add_argument("--out-dir", type=Path, default=Path("artifacts/eval"))
    ap.add_argument("--limit", type=int, default=None, help="Cap events for quick dry-run")
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    baseline = BaselineDetector(window=args.baseline_window, stddev_threshold=args.baseline_std)
    snn = SNNDetector()
    snn.threshold = float(args.snn_threshold)

    # Metrics accumulators
    base_tp = base_fp = base_fn = 0
    snn_tp = snn_fp = snn_fn = 0
    base_pred_events = 0
    snn_pred_events = 0
    total = 0
    snn_latencies = []  # seconds
    baseline_latencies = []
    baseline_anomaly_ids = set()
    snn_anomaly_ids = set()

    proc_before = psutil.Process(os.getpid()) if psutil else None
    rss_before = proc_before.memory_info().rss if proc_before else None

    for ev in load_events(args.path):
        total += 1
        if args.limit and total > args.limit:
            break
        is_true = bool(getattr(ev, 'labels', {}).get("is_anomaly"))

        t0 = time.perf_counter()
        base_res = baseline.process(ev)
        baseline_latencies.append(time.perf_counter() - t0)
        base_pred = bool(base_res)
        if base_pred:
            base_pred_events += 1
            baseline_anomaly_ids.add(ev.event_id)
            if is_true:
                base_tp += 1
            else:
                base_fp += 1
        else:
            if is_true:
                base_fn += 1

        t1 = time.perf_counter()
        snn_res = snn.process(ev)
        t2 = time.perf_counter()
        snn_pred = bool(snn_res)
        snn_latencies.append(t2 - t1 if not snn_res else snn_res[0].get("inference_latency_s", t2 - t1))
        if snn_pred:
            snn_pred_events += 1
            snn_anomaly_ids.add(ev.event_id)
            if is_true:
                snn_tp += 1
            else:
                snn_fp += 1
        else:
            if is_true:
                snn_fn += 1

    # Compute metrics
    base_metrics = compute_pr_metrics(base_tp, base_fp, base_fn)
    snn_metrics = compute_pr_metrics(snn_tp, snn_fp, snn_fn)

    def lat_summary(vals):
        return {
            "count": len(vals),
            "p50_ms": percentile(vals, 0.5) * 1000.0,
            "p95_ms": percentile(vals, 0.95) * 1000.0,
            "mean_ms": (statistics.fmean(vals) * 1000.0) if vals else 0.0,
        }

    base_latency_stats = lat_summary(baseline_latencies)
    snn_latency_stats = lat_summary(snn_latencies)

    overlap = len(baseline_anomaly_ids & snn_anomaly_ids)
    union = len(baseline_anomaly_ids | snn_anomaly_ids) or 1
    overlap_ratio = overlap / union

    uplifts = {
        "recall_uplift": (snn_metrics["recall"] - base_metrics["recall"]) / base_metrics["recall"] if base_metrics["recall"] else 0.0,
        "precision_loss": (base_metrics["precision"] - snn_metrics["precision"]),
        "f1_uplift": snn_metrics["f1"] - base_metrics["f1"],
    }
    overhead = {
        "added_latency_p95_ms": snn_latency_stats["p95_ms"] - base_latency_stats["p95_ms"],
    }
    decision = decide(uplifts, overhead)

    # Memory / CPU delta snapshot (approx)
    rss_after = proc_before.memory_info().rss if proc_before else None
    rss_delta_mb = ((rss_after - rss_before) / (1024 * 1024)) if (rss_before and rss_after) else None
    cpu_percent = proc_before.cpu_percent(interval=0.05) if proc_before else None  # short sample

    combined = {
        "total_events": total,
        "baseline": {
            **base_metrics,
            "predicted_anomaly_events": base_pred_events,
            "latency": base_latency_stats,
        },
        "snn": {
            **snn_metrics,
            "predicted_anomaly_events": snn_pred_events,
            "latency": snn_latency_stats,
            "threshold": snn.threshold,
        },
        "overlap": {
            "baseline_only": len(baseline_anomaly_ids - snn_anomaly_ids),
            "snn_only": len(snn_anomaly_ids - baseline_anomaly_ids),
            "overlap": overlap,
            "overlap_ratio": overlap_ratio,
            "sample_baseline_only": list((baseline_anomaly_ids - snn_anomaly_ids))[:20],
            "sample_snn_only": list((snn_anomaly_ids - baseline_anomaly_ids))[:20],
        },
        "uplifts": uplifts,
        "overhead": overhead,
        "resources_snapshot": {
            "rss_delta_mb": rss_delta_mb,
            "cpu_percent_sample": cpu_percent,
        },
        "decision": decision,
        "spec_hash_refs": {
            "uplift_targets_doc": "docs/UPLIFT_TARGETS.md",
            "resource_budget_doc": "docs/RESOURCE_BUDGET.md",
        },
    }

    # Write artifacts
    snn_only_artifact = {
        "snn": combined["snn"],
        "uplifts": uplifts,
        "latency": snn_latency_stats,
    }
    snn_path = args.out_dir / "snn_metrics.json"
    with snn_path.open("w", encoding="utf-8") as f:
        json.dump(snn_only_artifact, f, indent=2)
    combined_path = args.out_dir / "baseline_vs_snn_eval.json"
    with combined_path.open("w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2)
    print(json.dumps(combined, indent=2))
    print(f"Wrote SNN metrics: {snn_path}")
    print(f"Wrote combined evaluation: {combined_path}")


if __name__ == "__main__":  # pragma: no cover
    main()
