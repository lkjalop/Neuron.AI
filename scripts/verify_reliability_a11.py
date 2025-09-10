"""A11 Reliability Verification Script.

Generates reliability evidence that anomalies are produced post-ingest.
Outputs artifacts/reliability/reliability_report_<ts>.json with:
  events, anomalies_total, anomaly_log_hash (if present), param_hash, detectors, timestamp
Exit code non-zero if criteria not met (e.g., anomalies == 0).
"""
from __future__ import annotations
import json, time, pathlib, hashlib, random
from config import runtime_params
from core.detect.interface import registry
from core.event import Event
from core.shared_anomalies import anomaly_buffer

OUT_DIR = pathlib.Path("artifacts/reliability")
ANOMALY_LOG = pathlib.Path("anomaly_log.jsonl")


def sha256_file(p: pathlib.Path) -> str:
    if not p.exists():
        return "0" * 64
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def param_snapshot_hash() -> str:
    snap = runtime_params.list_params()
    payload = json.dumps(snap, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main():
    # Generate synthetic events
    tenants = ["tenantA", "tenantB"]
    for i in range(200):
        t = random.choice(tenants)
        ev = Event(
            event_id=f"rel_{i}",
            tenant_id=t,
            trace_id=None,
            features={"value": random.gauss(0, 1)},
            raw={},
            ts=time.time(),
        )
        for det in registry.detectors():
            try:
                det.process(ev)
            except Exception:
                pass
    # Gather anomalies
    total = 0
    for t in tenants:
        total += len(anomaly_buffer.recent(t, 500))
    report = {
        "ts": time.time(),
        "events": 200,
        "anomalies_total": total,
        "anomaly_log_hash": sha256_file(ANOMALY_LOG),
        "param_hash": param_snapshot_hash(),
        "detectors": [getattr(d, "name", "unknown") for d in registry.detectors()],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUT_DIR / f"reliability_report_{int(time.time())}.json"
    out_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if total == 0:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
