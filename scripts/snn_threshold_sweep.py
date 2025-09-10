"""Sweep SNN threshold values to find a governance-compliant operating point.

Uses existing dual evaluation harness internally for consistency.

Criteria (from docs/UPLIFT_TARGETS.md):
  - recall uplift >= 0.15
  - precision loss <= 0.05
Selects the lowest threshold meeting both (to avoid over-triggering) else reports failure.

Usage:
  python scripts/snn_threshold_sweep.py --events events.jsonl --thresholds 1 2 3 4 5 6 7 8
"""
from __future__ import annotations
import argparse, json, subprocess, sys, pathlib, time
from typing import List, Dict, Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "artifacts" / "eval"
EVAL_DIR.mkdir(parents=True, exist_ok=True)

def run_eval(events: str, threshold: float, window: int, base_std: float) -> Dict[str, Any]:
    cmd = [sys.executable, "scripts/evaluate_snn.py", events, "--baseline-window", str(window), "--baseline-std", str(base_std), "--snn-threshold", str(threshold)]
    start = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    duration = time.time() - start
    result: Dict[str, Any] = {"threshold": threshold, "duration_sec": duration}
    if proc.returncode != 0:
        result["error"] = proc.stderr.strip()[:400]
        return result
    # Parse JSON from stdout (evaluate_snn prints exactly one object)
    try:
        # Find first '{' and last '}' to be robust against stray warnings
        out = proc.stdout
        start_i = out.find('{')
        end_i = out.rfind('}')
        if start_i != -1 and end_i != -1 and end_i > start_i:
            data = json.loads(out[start_i:end_i+1])
            result.update(data)
        else:
            result['error'] = 'no_json'
    except Exception as e:  # noqa: BLE001
        result['error'] = f'parse_error:{e}'[:200]
    return result

def governance_ok(r: Dict[str, Any]) -> bool:
    uplifts = r.get('uplifts') or {}
    recall_uplift = uplifts.get('recall_uplift', 0.0)
    precision_loss = uplifts.get('precision_loss', 1.0)
    return recall_uplift >= 0.15 and precision_loss <= 0.05

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--events', required=True)
    ap.add_argument('--thresholds', type=float, nargs='+', required=True, help='List of SNN thresholds to test')
    ap.add_argument('--baseline-window', type=int, default=50)
    ap.add_argument('--baseline-std', type=float, default=2.0)
    ap.add_argument('--out', default=str(EVAL_DIR / 'snn_threshold_sweep.json'))
    args = ap.parse_args()

    results: List[Dict[str, Any]] = []
    best = None
    for t in args.thresholds:
        print(f'[+] Evaluating SNN threshold={t}')
        r = run_eval(args.events, t, args.baseline_window, args.baseline_std)
        results.append(r)
        if not r.get('error') and governance_ok(r):
            # pick first (lowest threshold) satisfying governance targets
            if best is None:
                best = r
    summary = {
        'thresholds': args.thresholds,
        'results': results,
        'selected': best,
        'selected_value': best.get('snn', {}).get('threshold') if best else None,
        'governance_satisfied': bool(best),
    }
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))
    if not best:
        print('No governance-compliant threshold found; consider model/scoring adjustments.', file=sys.stderr)

if __name__ == '__main__':  # pragma: no cover
    main()
