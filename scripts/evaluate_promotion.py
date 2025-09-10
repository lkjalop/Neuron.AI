"""Evaluate promotion gates for optional detectors (SNN, Isolation Forest).

Reads anomaly log (artifacts/dataset/anomaly_log.jsonl) and computes:
 - total anomalies per detector
 - unique contribution ratio (anomalies where only that detector fired for an event_id)
 - overlap counts

Promotion Heuristics (baseline draft):
 - Detector must contribute >= MIN_PERCENT total anomalies (default 0.05)
 - Unique contribution ratio >= MIN_UNIQUE (default 0.02)
 - (Future) precision proxy degradation not negative beyond threshold

Outputs JSON artifact in artifacts/gate_report/promotion_eval_<timestamp>.json
and prints PASS/FAIL per candidate.
"""
from __future__ import annotations
import argparse, json, pathlib, time, collections
from typing import Dict, List, Set

DEFAULT_MIN_PERCENT = 0.05
DEFAULT_MIN_UNIQUE = 0.02


def load_anomalies(path: pathlib.Path) -> List[dict]:
    if not path.exists():
        return []
    out = []
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def evaluate(anomalies: List[dict], min_percent: float, min_unique: float):
    if not anomalies:
        return {"error": "no_anomalies"}
    # Group by event_id
    by_event: Dict[str, List[dict]] = collections.defaultdict(list)
    for a in anomalies:
        eid = a.get("event_id")
        if eid:
            by_event[eid].append(a)
    total = len(anomalies)
    per_detector = collections.Counter(a.get("detector") for a in anomalies)
    unique_contrib = collections.Counter()
    overlap = 0
    for eid, group in by_event.items():
        if len(group) == 1:
            unique_contrib[group[0].get("detector")] += 1
        else:
            overlap += 1
    results = {}
    for det, count in per_detector.items():
        if not det:
            continue
        pct = count / total
        u_ratio = unique_contrib.get(det, 0) / total
        pass_min_pct = pct >= min_percent
        pass_unique = u_ratio >= min_unique
        results[det] = {
            "count": count,
            "percent_total": round(pct, 4),
            "unique_contribution_ratio": round(u_ratio, 4),
            "passes": bool(pass_min_pct and pass_unique),
            "criteria": {
                "min_percent": min_percent,
                "min_unique": min_unique,
            },
        }
    return {
        "total_anomalies": total,
        "overlap_events": overlap,
        "detectors": results,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anomaly-log", default="artifacts/dataset/anomaly_log.jsonl")
    ap.add_argument("--min-percent", type=float, default=DEFAULT_MIN_PERCENT)
    ap.add_argument("--min-unique", type=float, default=DEFAULT_MIN_UNIQUE)
    ap.add_argument("--out-dir", default="artifacts/gate_report")
    args = ap.parse_args()
    anomalies = load_anomalies(pathlib.Path(args.anomaly_log))
    report = evaluate(anomalies, args.min_percent, args.min_unique)
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"promotion_eval_{ts}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"Promotion evaluation written: {out_path}")
    if isinstance(report, dict) and 'detectors' in report:
        for det, info in report['detectors'].items():
            status = "PASS" if info['passes'] else "FAIL"
            print(f"Detector {det}: {status} (percent={info['percent_total']}, unique={info['unique_contribution_ratio']})")


if __name__ == "__main__":
    main()
