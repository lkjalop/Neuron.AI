"""Dataset export stub.

Exports recent anomalies plus associated lightweight feature snapshot for
offline labeling / model experimentation. This is intentionally minimal and
non-destructive. Future enhancements: pagination, feature enrichment, 
redaction policies, tenant scoping with IAM.

Outputs:
  artifacts/dataset/anomalies_<epoch>.jsonl  (raw anomaly docs)
  artifacts/dataset/manifest_<epoch>.json    (metadata: param snapshot, counts)

Usage:
  python scripts/export_dataset.py --limit 500 --tenant tenantA
"""
from __future__ import annotations

import argparse, json, os, time, sys, pathlib

# Ensure src is on path for standalone invocation without PYTHONPATH env.
_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
from pathlib import Path
from typing import List, Dict, Any

# Lazy imports to avoid circulars at import time
from core.shared_anomalies import anomaly_buffer
from config import runtime_params


def export_anomalies(tenant: str | None, limit: int) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    if tenant:
        results = anomaly_buffer.recent(tenant, limit)
    else:
        # aggregate across all tenants up to limit each
        for t in anomaly_buffer.tenants():
            results.extend(anomaly_buffer.recent(t, limit))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", default=None, help="Limit export to tenant (default: all)")
    ap.add_argument("--limit", type=int, default=500, help="Max anomalies per tenant")
    ap.add_argument("--out-dir", default="artifacts/dataset")
    args = ap.parse_args()

    ts = int(time.time())
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    anomalies = export_anomalies(args.tenant, args.limit)
    if not anomalies:  # cross-process hydration attempt
        anomaly_buffer.replay_persisted()
        anomalies = export_anomalies(args.tenant, args.limit)
    anomalies_path = out_dir / f"anomalies_{ts}.jsonl"
    with anomalies_path.open("w", encoding="utf-8") as f:
        for a in anomalies:
            f.write(json.dumps(a) + "\n")

    manifest = {
        "export_ts": ts,
        "tenant": args.tenant,
        "anomaly_count": len(anomalies),
        "params_snapshot": runtime_params.list_params(),
        "notes": "Dataset export stub v1; fields subject to extension.",
    }
    manifest_path = out_dir / f"manifest_{ts}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps({
        "anomalies_file": str(anomalies_path),
        "manifest_file": str(manifest_path),
        "anomaly_count": len(anomalies)
    }, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
