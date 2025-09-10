"""Compare detector precision proxy & unique contribution metrics.

Reads anomaly log + (optional) metrics scrape snapshot (future). For now,
derives precision proxy stats from counters if orchestrator previously updated
`neuron_precision_proxy_false_positive_total` and `neuron_precision_proxy_windows_total` by re-processing anomaly log alongside stored noise flags (not persisted yet) – so we approximate using anomaly log only (precision proxy counts rely on metrics in-memory). As a fallback, this script reruns a synthetic pass to compute current gauge values for active detectors and includes union/unique ratio queries via internal registry.

Output JSON: artifacts/perf/compare_detectors_<timestamp>.json
"""
from __future__ import annotations
import argparse, json, time, pathlib, os
from typing import Dict, List

from detect.orchestrator import build_default_orchestrator, Anomaly
from core.event import Event


def synthetic_probe(detectors: List[str], tenant: str = "cmp") -> Dict[str, float]:
    # Generate a small deterministic event stream to touch detectors so they initialize gauges
    events: List[Event] = []
    for i in range(40):
        sev = 10.0 + (i % 5)
        events.append(Event.create(event_type="cmp", severity=sev, tenant_id=tenant, features={"f0": sev, "f1": sev * 0.2}))
    orch = build_default_orchestrator()
    anomalies: List[Anomaly] = []
    for ev in events:
        anomalies.extend(orch.process_event(ev))
    orch.flush()
    # Summaries
    counts: Dict[str, int] = {}
    for a in anomalies:
        counts[a.detector] = counts.get(a.detector, 0) + 1
    return {d: counts.get(d, 0) for d in detectors}


def load_anomaly_log(path: pathlib.Path) -> List[dict]:
    out: List[dict] = []
    if not path.exists():
        return out
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--anomaly-log', default='artifacts/dataset/anomaly_log.jsonl')
    ap.add_argument('--out', default='artifacts/perf/compare_detectors.json')
    args = ap.parse_args()
    anomalies = load_anomaly_log(pathlib.Path(args.anomaly_log))
    detector_counts: Dict[str, int] = {}
    event_detector_sets: Dict[str, set] = {}
    for a in anomalies:
        det = a.get('detector')
        if not det:
            continue
        detector_counts[det] = detector_counts.get(det, 0) + 1
        eid = a.get('event_id')
        if eid:
            event_detector_sets.setdefault(eid, set()).add(det)
    unique_counts: Dict[str, int] = {}
    overlap_counts: Dict[str, int] = {}
    for eid, ds in event_detector_sets.items():
        if len(ds) == 1:
            d = next(iter(ds))
            unique_counts[d] = unique_counts.get(d, 0) + 1
        else:
            for d in ds:
                overlap_counts[d] = overlap_counts.get(d, 0) + 1
    union_events = len(event_detector_sets)
    unique_ratio = {d: (unique_counts.get(d, 0) / union_events) if union_events else 0.0 for d in detector_counts}

    # Synthetic probe to ensure detectors reachable now
    active = list(detector_counts.keys()) or ["baseline_stats"]
    synthetic_counts = synthetic_probe(active)

    report = {
        'total_anomalies': sum(detector_counts.values()),
        'detector_counts': detector_counts,
        'unique_counts': unique_counts,
        'overlap_counts': overlap_counts,
        'unique_ratio': unique_ratio,
        'union_events': union_events,
        'synthetic_counts': synthetic_counts,
        'generated_at': time.time(),
    }
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"Detector comparison written: {out_path}")
    for d, c in detector_counts.items():
        print(f"{d}: anomalies={c} unique_ratio={unique_ratio.get(d,0):.3f}")


if __name__ == '__main__':
    main()
