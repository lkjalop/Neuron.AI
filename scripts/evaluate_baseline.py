"""Evaluate baseline detector on synthetic events JSONL.

Example:
  python scripts/generate_synthetic_events.py --count 500 > events.jsonl
  python scripts/evaluate_baseline.py events.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
import statistics  # noqa: F401  (kept for backward compat / potential future use)
import os  # noqa: F401

from core.detect.baseline import BaselineDetector
from core.event import validate_event, dict_to_event, Event
try:
    # Prefer shared loader if available
    from scripts.eval_utils import load_labeled_events as _shared_load_events  # type: ignore
except Exception:  # noqa: BLE001
    _shared_load_events = None


def load_events(path: Path):
    """Backward compatible loader; delegates to shared util if present."""
    if _shared_load_events:
        yield from _shared_load_events(path)
        return
    with path.open(encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            try:
                raw = json.loads(s)
            except json.JSONDecodeError:
                print(f"WARN: Could not parse JSON on line {idx}", file=sys.stderr)
                continue
            try:
                ev = dict_to_event(raw)
                yield ev
            except Exception as e:  # noqa: BLE001
                print(f"WARN: Could not convert line {idx} to Event: {e}", file=sys.stderr)
                continue


def compute_metrics(tp: int, fp: int, fn: int) -> Dict[str, Any]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def main():
    ap = argparse.ArgumentParser(description="Evaluate baseline detector producing precision/recall/F1 metrics artifact.")
    ap.add_argument("path", type=Path, help="Input JSONL synthetic events with labels")
    ap.add_argument("--window", type=int, default=50)
    ap.add_argument("--std", type=float, default=3.0)
    ap.add_argument("--out-dir", type=Path, default=Path("artifacts/eval"))
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    det = BaselineDetector(window=args.window, stddev_threshold=args.std)
    total = 0
    predicted_positive_events = 0
    tp = fp = fn = 0
    for ev in load_events(args.path):
        validate_event(ev)
        res = det.process(ev)
        is_pred = bool(res)
        is_true = bool(getattr(ev, 'labels', {}).get("is_anomaly"))
        total += 1
        if is_pred:
            predicted_positive_events += 1
            if is_true:
                tp += 1
            else:
                fp += 1
        else:
            if is_true:
                fn += 1

    m = compute_metrics(tp, fp, fn)
    output = {
        "total_events": total,
        "predicted_anomaly_events": predicted_positive_events,
        "predicted_anomaly_rate": predicted_positive_events / total if total else 0.0,
        "window": args.window,
        "stddev_threshold": args.std,
        **m,
    }
    artifact_path = args.out_dir / "baseline_metrics.json"
    with artifact_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(json.dumps(output, indent=2))
    print(f"Wrote evaluation artifact to {artifact_path}")


if __name__ == "__main__":
    main()
