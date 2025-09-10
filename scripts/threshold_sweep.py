"""Threshold sweep helper.

Runs baseline evaluation across multiple stddev thresholds and emits summary JSON.

Usage:
  python scripts/generate_synthetic_events.py --count 800 > events.jsonl
  python scripts/threshold_sweep.py --events events.jsonl --thresholds 2.0 2.5 3.0 3.5 4.0
"""
from __future__ import annotations

import argparse, json, subprocess, sys, pathlib, time
from typing import List, Dict, Any

# Allow script to update runtime parameters if desired
try:  # local import path adjustment
    from config import runtime_params  # type: ignore
except Exception:  # pragma: no cover
    runtime_params = None  # type: ignore

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "artifacts" / "eval"
EVAL_DIR.mkdir(parents=True, exist_ok=True)


def run_eval(events: str, window: int, threshold: float) -> Dict[str, Any]:
    cmd = [sys.executable, "scripts/evaluate_baseline.py", events, "--window", str(window), "--std", str(threshold), "--out-dir", str(EVAL_DIR)]
    start = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    duration = time.time() - start
    result: Dict[str, Any] = {"threshold": threshold, "duration_sec": duration}
    if proc.returncode != 0:
        result["error"] = proc.stderr.strip()[:400]
        return result
    try:
        # Capture first JSON object block
        text = proc.stdout
        start = text.find('{')
        end = text.find('}\n', start)
        if start != -1 and end != -1:
            block = text[start:end+1]
            data = json.loads(block)
            result.update(data)
        else:
            result["error"] = "No JSON metrics captured"
    except Exception as e:  # noqa: BLE001
        result["error"] = f"parse_error: {e}"[:200]
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", required=True, help="Path to synthetic events JSONL")
    ap.add_argument("--thresholds", nargs="*", type=float, default=[2.0, 2.5, 3.0, 3.5])
    ap.add_argument("--window", type=int, default=50)
    ap.add_argument("--out", default=str(EVAL_DIR / "threshold_sweep.json"))
    ap.add_argument("--apply-best", action="store_true", help="Update runtime param baseline.stddev_threshold with best F1 and persist defaults (audited)")
    args = ap.parse_args()

    results: List[Dict[str, Any]] = []
    for t in args.thresholds:
        print(f"[+] Evaluating threshold={t}")
        r = run_eval(args.events, args.window, t)
        results.append(r)
    # choose best by F1 if available
    valid = [r for r in results if r.get("f1") is not None]
    best = None
    if valid:
        best = max(valid, key=lambda x: x.get("f1", -1))

    summary = {
        "window": args.window,
        "thresholds": args.thresholds,
        "results": results,
        "best": best,
        "applied": False,
    }
    if args.apply_best and best and runtime_params:
        chosen = best.get("stddev_threshold") or best.get("threshold")
        if chosen is not None:
            try:
                runtime_params.update_param("baseline.stddev_threshold", float(chosen), reason="threshold_sweep_best_f1", actor="threshold_sweep")
                # persist all params to defaults file so restarts keep the new threshold
                if hasattr(runtime_params, "save_defaults"):
                    runtime_params.save_defaults()
                summary["applied"] = True
                summary["applied_value"] = chosen
            except Exception as e:  # noqa: BLE001
                summary["apply_error"] = str(e)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))
    print(f"Wrote threshold sweep summary to {args.out}")

if __name__ == "__main__":  # pragma: no cover
    main()
