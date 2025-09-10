"""Generate synthetic events (with optional labeled anomalies) to JSONL.

Usage:
    powershell:
        python scripts/generate_synthetic_events.py --count 1000 --tenants t1 t2 --anomaly-rate 0.1 --seed 42 --emit-manifest events.manifest.json > events.jsonl

Design:
- Normal feature values sampled from base uniform(0,1) or normal distribution.
- Anomalies injected with amplified magnitude (e.g., +anomaly_magnitude or negative spike) and label `labels.is_anomaly=true`.
- Deterministic RNG seed accepted for reproducibility.
- Optional manifest file (JSON) records deterministic parameters & SHA256 hashes so future real data replacement is auditable.

Real Data Substitution Guidance:
- When replacing with real SIEM/SOAR/Firewall/IDS or cloud telemetry, keep the manifest schema stable; add a `source.type` field describing connector (e.g., `siem.splunk`, `siem.sentinel`, `observability.datadog`).
- Avoid embedding PII / secrets; ensure pre-scrubbing before ingest.
"""
from __future__ import annotations

import argparse, json, random, time, math, hashlib, sys
from pathlib import Path


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def gen_event(tenant: str, is_anom: bool, magnitude: float, idx: int, seed: int | None):
    base = random.random()
    if is_anom:
        # Shift value outside typical [0,1] range to trigger z-score / MAD
        direction = 1 if random.random() < 0.5 else -1
        val = base + direction * magnitude
    else:
        val = base
    return {
        "tenant_id": tenant,
        "timestamp": time.time(),
        "source": random.choice(["proc", "net", "fs"]),
        "raw": {"cpu": val},
        "features": {"cpu": val},
        "labels": {"is_anomaly": is_anom},
        "meta": {
            "synthetic": True,
            "sequence_index": idx,
            "seed": seed,
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=100)
    ap.add_argument("--tenants", nargs="*", default=["tenantA"])
    ap.add_argument("--anomaly-rate", type=float, default=0.05, help="Fraction of events labeled anomalies (0-1)")
    ap.add_argument("--anomaly-magnitude", type=float, default=5.0, help="Magnitude shift applied to anomaly events")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--emit-manifest", type=Path, default=None, help="Optional path to write dataset manifest JSON")
    ap.add_argument("--out-file", type=Path, default=None, help="Write events to this file instead of stdout")
    args = ap.parse_args()
    if args.seed is not None:
        random.seed(args.seed)
    anomalies_target = int(args.count * args.anomaly_rate)
    anomalies_remaining = anomalies_target
    event_hashes: list[str] = []
    # Decide sink: file or stdout
    sink_file = None
    if args.out_file:
        args.out_file.parent.mkdir(parents=True, exist_ok=True)
        sink_file = args.out_file.open("w", encoding="utf-8", newline="\n")
    write = (lambda s: sys.stdout.write(s + "\n")) if sink_file is None else (lambda s: sink_file.write(s + "\n"))
    for i in range(args.count):
        tenant = random.choice(args.tenants)
        # Simple strategy: spread anomalies roughly evenly
        remaining_events = args.count - i
        # Decide anomaly if we still need to place them and probability fits
        is_anom = False
        if anomalies_remaining > 0:
            # Probability heuristic to distribute anomalies
            if random.random() < anomalies_remaining / remaining_events:
                is_anom = True
                anomalies_remaining -= 1
        evt = gen_event(tenant, is_anom, args.anomaly_magnitude, i, args.seed)
        line = json.dumps(evt)
        event_hashes.append(sha256_text(line))
        write(line)
    if sink_file:
        sink_file.close()

    if args.emit_manifest:
        manifest = {
            "schema": "synthetic.dataset.v1",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "parameters": {
                "count": args.count,
                "tenants": args.tenants,
                "anomaly_rate": args.anomaly_rate,
                "anomaly_magnitude": args.anomaly_magnitude,
                "seed": args.seed,
            },
            "event_count": len(event_hashes),
            "events_merkle_root": sha256_text("".join(event_hashes)),
            "notes": "Replaceable with real telemetry: maintain schema, extend parameters.source.* for real connectors.",
        }
        args.emit_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Wrote dataset manifest to {args.emit_manifest}", file=sys.stderr)


if __name__ == "__main__":
    main()
