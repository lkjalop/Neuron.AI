"""Run a simple end-to-end detection + evidence bundling flow.

Generates synthetic events with occasional anomalies (severity spikes), runs
the detector orchestrator (baseline + optional Isolation Forest), and produces:
 - artifacts/dataset/anomaly_log.jsonl (appended)
 - artifacts/forensics/case_*/ case directories

Usage (PowerShell):
  $env:EXPERIMENTAL_ISOFOREST="true"  # optional
  python scripts/run_detection_pipeline.py --events 300 --tenant demo
"""
from __future__ import annotations
import argparse, random, time
from typing import List

from core.event import Event
from detect.orchestrator import build_default_orchestrator, Anomaly
from forensics.evidence import EvidenceBundler

try:
    from detect.isolation_forest_detector import IsolationForestDetector
except Exception:
    IsolationForestDetector = None  # type: ignore


def generate_events(n: int, tenant: str) -> List[Event]:
    events: List[Event] = []
    baseline = 10.0
    for i in range(n):
        # Introduce periodic anomaly spikes
        if i % 57 == 0 and i > 0:
            sev = baseline + random.uniform(15, 25)
        else:
            sev = baseline + random.uniform(-2, 2)
        ev = Event.create(
            event_type="synthetic", tenant_id=tenant, severity=sev,
            features={"f0": sev, "f1": sev * 0.5 + random.random()}
        )
        events.append(ev)
    return events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", type=int, default=200)
    ap.add_argument("--tenant", type=str, default="global")
    args = ap.parse_args()

    orch = build_default_orchestrator()
    # Dynamically add Isolation Forest if available
    if IsolationForestDetector is not None:
        try:
            orch.registry.register(IsolationForestDetector())
            print("IsolationForestDetector enabled")
        except Exception as e:
            print(f"IsolationForestDetector not enabled: {e}")

    events = generate_events(args.events, args.tenant)
    anomalies: List[Anomaly] = []
    for ev in events:
        anomalies.extend(orch.process_event(ev))
    orch.flush()
    print(f"Processed {len(events)} events -> {len(anomalies)} anomalies")

    bundler = EvidenceBundler()
    cases = bundler.bundle(events, anomalies)
    print(f"Created {len(cases)} cases")
    for c in cases[:5]:
        print(f"Case {c.case_id} anomalies={c.anomaly_count} detectors={','.join(sorted(c.detectors))}")


if __name__ == "__main__":
    main()
