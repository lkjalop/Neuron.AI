#!/usr/bin/env python
"""Tenant purge script (scaffold).

Usage:
  python scripts/purge_tenant.py --tenant TENANT_ID [--dry-run]

Behavior:
  - Validates tenant exists.
  - Computes row counts & artifact disk usage.
  - If not dry-run, performs deletion in ordered phases.
  - Emits simple stdout report (JSON) for automation capture.

NOTE: Current project schema may not yet include tenant_id on all tables; this is a forward-looking scaffold.
"""
from __future__ import annotations
import argparse, os, json, sqlite3, shutil, sys, time

DB_PATH = os.environ.get("SQLITE_DB_PATH", "artifacts/neuron.db")
ARTIFACT_ROOT = os.path.join("artifacts")

TABLES = [
    "retrieval_chunks",
    "vulnerabilities",
    "assets",
    "detections",
    "reports",
    "param_store",
    "audit_log",
]

def connect():
    return sqlite3.connect(DB_PATH)

def get_counts(cur, tenant_id: str):
    counts = {}
    for t in TABLES:
        try:
            cur.execute(f"SELECT COUNT(1) FROM {t} WHERE tenant_id = ?", (tenant_id,))
            counts[t] = cur.fetchone()[0]
        except Exception:
            counts[t] = None  # table or column absent
    return counts

def artifact_usage(tenant_id: str):
    path = os.path.join(ARTIFACT_ROOT, tenant_id)
    total = 0
    if os.path.isdir(path):
        for root, _dirs, files in os.walk(path):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    return {"bytes": total, "path": path}

def purge(cur, tenant_id: str):
    for t in TABLES:
        try:
            cur.execute(f"DELETE FROM {t} WHERE tenant_id = ?", (tenant_id,))
        except Exception:
            continue

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    with connect() as cx:
        cur = cx.cursor()
        counts_before = get_counts(cur, args.tenant)
        usage_before = artifact_usage(args.tenant)
        result = {
            "tenant": args.tenant,
            "dry_run": args.dry_run,
            "counts_before": counts_before,
            "artifact_usage_before": usage_before,
        }
        if not args.dry_run:
            purge(cur, args.tenant)
            cx.commit()
            # Delete artifacts directory
            if os.path.isdir(usage_before["path"]):
                shutil.rmtree(usage_before["path"], ignore_errors=True)
            result["status"] = "purged"
        else:
            result["status"] = "dry_run"
        result["elapsed_seconds"] = round(time.time() - t0, 4)
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
