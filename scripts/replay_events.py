"""Replay a JSONL events dataset through the orchestrator.

Input format: each line JSON with keys accepted by core.event.dict_to_event (at minimum event_type, optional severity, features, tenant_id).
Usage:
  python scripts/replay_events.py --input path/to/events.jsonl --summary artifacts/perf/replay_summary.json

Outputs:
  - Updated anomaly_log.jsonl (append mode)
  - Summary JSON with per-detector counts, total events, anomalies, precision proxy window stats.
"""
from __future__ import annotations
import argparse, json, pathlib
from typing import List, Dict

from core.event import dict_to_event, Event
from detect.orchestrator import build_default_orchestrator, Anomaly


def load_events(path: pathlib.Path) -> List[Event]:
    events: List[Event] = []
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except Exception:
                continue
            try:
                events.append(dict_to_event(raw))
            except Exception:
                continue
    return events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True, help='Path to JSONL events file')
    ap.add_argument('--summary', default='artifacts/perf/replay_summary.json')
    args = ap.parse_args()
    in_path = pathlib.Path(args.input)
    events = load_events(in_path)
    orch = build_default_orchestrator()
    anomalies: List[Anomaly] = []
    for ev in events:
        anomalies.extend(orch.process_event(ev))
    orch.flush()
    # Aggregate counts
    per_detector: Dict[str, int] = {}
    for a in anomalies:
        per_detector[a.detector] = per_detector.get(a.detector, 0) + 1
    summary = {
        'input_file': str(in_path),
        'total_events': len(events),
        'total_anomalies': len(anomalies),
        'per_detector': per_detector,
    }
    out_path = pathlib.Path(args.summary)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(f"Replay complete. Summary written: {out_path}")
    for det, c in per_detector.items():
        print(f"  {det}: {c}")


if __name__ == '__main__':
    main()
