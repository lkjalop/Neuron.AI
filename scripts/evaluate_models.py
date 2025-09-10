"""Evaluate multiple detectors / fusion strategies and produce comparative metrics.

Usage:
  python scripts/evaluate_models.py events.jsonl --detectors baseline snn --bootstrap 500 --seed 42 \
      --utility-weights 0.4 0.6 0.2

If a detector is not available (e.g., SNN flag off) it will be skipped gracefully.
Outputs JSON artifact at artifacts/eval/comparison_metrics.json with structure:
{
  "detectors": {
     "baseline": { metrics ... },
     "snn": { metrics ... }
  },
  "pairs": {
     "baseline_vs_snn": { "mcnemar": {...}, "delta_f1": ..., "delta_utility": ... }
  }
}

Bootstrap procedure:
  - For each metric needing CI (f1, utility) we resample event indices with replacement
    and recompute metric for each detector, storing distribution.
  - Report percentile interval (alpha/2, 1-alpha/2).

Utility score default weights: w_p=0.3, w_r=0.7, w_fp=0.2 (penalize FP rate).
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path
from typing import Dict, Any, List

from core.detect.baseline import BaselineDetector
try:
    from core.detect.snn import SNNDetector  # type: ignore
except Exception:  # noqa: BLE001
    SNNDetector = None  # type: ignore

from core.event import validate_event, Event
from scripts.eval_utils import (
    set_seed,
    load_labeled_events,
    compute_confusion,
    metric_dict,
    bootstrap_ci,
    utility_score,
    mcnemar,
)


def parse_args():
    ap = argparse.ArgumentParser(description="Evaluate multiple detectors/fusion strategies with statistical rigor.")
    ap.add_argument("path", type=Path, help="Input labeled events JSONL")
    ap.add_argument("--detectors", nargs="*", default=["baseline"], help="Detectors to evaluate (baseline, snn)")
    ap.add_argument("--window", type=int, default=50)
    ap.add_argument("--std", type=float, default=3.0)
    ap.add_argument("--bootstrap", type=int, default=1000)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--utility-weights", nargs=3, type=float, default=[0.3, 0.7, 0.2], metavar=("W_P", "W_R", "W_FP"))
    ap.add_argument("--out-dir", type=Path, default=Path("artifacts/eval"))
    return ap.parse_args()


def build_detectors(names: List[str], window: int, std: float):
    created = {}
    for name in names:
        if name == "baseline":
            created[name] = BaselineDetector(window=window, stddev_threshold=std)
        elif name == "snn":
            if SNNDetector is None:
                print("INFO: SNN detector unavailable; skipping", file=sys.stderr)
            else:
                try:
                    created[name] = SNNDetector()
                except Exception as e:  # noqa: BLE001
                    print(f"WARN: Could not init SNN detector: {e}", file=sys.stderr)
        else:
            print(f"WARN: Unknown detector '{name}' - skipping", file=sys.stderr)
    return created


def run_detectors(detectors: Dict[str, Any], events: List[Event]):
    # For each detector, produce binary predictions at event level: 1 if any anomaly
    predictions: Dict[str, List[int]] = {k: [] for k in detectors}
    truths: List[int] = []
    for ev in events:
        try:
            validate_event(ev)
        except Exception:
            continue
        truths.append(1 if ev.labels.get("is_anomaly") else 0)
        for name, det in detectors.items():
            try:
                res = det.process(ev) or []
            except Exception:
                res = []
            predictions[name].append(1 if res else 0)
    return predictions, truths


def bootstrap_metrics(predictions: Dict[str, List[int]], truths: List[int], n_resamples: int, alpha: float, w_p: float, w_r: float, w_fp: float):
    n = len(truths)
    if n == 0:
        return {}
    # Precompute per-detector base metrics and per-event contributions
    results = {}
    for name, preds in predictions.items():
        tp, fp, tn, fn = compute_confusion(preds, truths)
        base = metric_dict(tp, fp, tn, fn)
        util = utility_score(base["precision"], base["recall"], base["fp_rate"], w_p, w_r, w_fp)
        # Prepare per-event contribution vectors for bootstrapping
        # We recompute confusion inside each resample for correctness (O(n * resamples * detectors)) acceptable for n modest.
        f1_samples: List[float] = []
        util_samples: List[float] = []
        # Quick optimization: collect indices array outside loop
        import random
        for _ in range(n_resamples):
            idxs = [random.randrange(0, n) for _ in range(n)]
            tp_b = fp_b = tn_b = fn_b = 0
            for i in idxs:
                p = preds[i]
                t = truths[i]
                if p == 1 and t == 1:
                    tp_b += 1
                elif p == 1 and t == 0:
                    fp_b += 1
                elif p == 0 and t == 0:
                    tn_b += 1
                else:
                    fn_b += 1
            m = metric_dict(tp_b, fp_b, tn_b, fn_b)
            f1_samples.append(m["f1"])
            util_samples.append(utility_score(m["precision"], m["recall"], m["fp_rate"], w_p, w_r, w_fp))
        f1_low, f1_high = bootstrap_ci(f1_samples, n_resamples=n_resamples, alpha=alpha)
        u_low, u_high = bootstrap_ci(util_samples, n_resamples=n_resamples, alpha=alpha)
        results[name] = {
            **base,
            "utility": util,
            "f1_ci": [f1_low, f1_high],
            "utility_ci": [u_low, u_high],
        }
    return results


def pairwise_analysis(predictions: Dict[str, List[int]], truths: List[int], metrics: Dict[str, Any]):
    pairs = {}
    names = list(predictions.keys())
    if len(names) < 2:
        return pairs
    base_name = names[0]
    for other in names[1:]:
        mcn = mcnemar(predictions[base_name], predictions[other], truths)
        delta_f1 = metrics[other]["f1"] - metrics[base_name]["f1"]
        delta_utility = metrics[other]["utility"] - metrics[base_name]["utility"]
        pairs[f"{base_name}_vs_{other}"] = {
            "mcnemar": mcn,
            "delta_f1": delta_f1,
            "delta_utility": delta_utility,
        }
    return pairs


def main():
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    set_seed(args.seed)
    events = list(load_labeled_events(args.path))
    detectors = build_detectors(args.detectors, args.window, args.std)
    if not detectors:
        print("ERROR: No detectors initialized", file=sys.stderr)
        sys.exit(1)
    predictions, truths = run_detectors(detectors, events)
    w_p, w_r, w_fp = args.utility_weights
    det_metrics = bootstrap_metrics(predictions, truths, args.bootstrap, args.alpha, w_p, w_r, w_fp)
    pairs = pairwise_analysis(predictions, truths, det_metrics)
    output = {
        "config": {
            "bootstrap": args.bootstrap,
            "alpha": args.alpha,
            "seed": args.seed,
            "utility_weights": {"w_p": w_p, "w_r": w_r, "w_fp": w_fp},
            "detectors": list(detectors.keys()),
            "total_events": len(truths),
            "positive_events": sum(truths),
        },
        "detectors": det_metrics,
        "pairs": pairs,
    }
    out_path = args.out_dir / "comparison_metrics.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(json.dumps(output, indent=2))
    print(f"Wrote evaluation artifact to {out_path}")


if __name__ == "__main__":
    main()
