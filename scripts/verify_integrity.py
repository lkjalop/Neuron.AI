"""Integrity verification script.

Recomputes hashes of key artifacts listed in the latest gate report JSON and
verifies the canonical doc hash. Exits non-zero on mismatch.

Usage:
  python scripts/verify_integrity.py --gate artifacts/gate_report/gate_report_1756820787.json
"""
from __future__ import annotations
import argparse, json, hashlib, sys, os
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def verify(gate_path: Path) -> int:
    data = json.loads(gate_path.read_text(encoding='utf-8'))
    failures = []
    artifacts = data.get('artifacts', {})
    for key, meta in artifacts.items():
        p = Path(meta.get('path', ''))
        expected = meta.get('sha256')
        if not p.exists():
            failures.append(f"MISSING:{key}:{p}")
            continue
        actual = sha256(p)
        if actual != expected:
            failures.append(f"HASH_MISMATCH:{key}:{actual}!={expected}")
    # Canonical doc hash check
    canonical_hash = data.get('canonical_doc_hash')
    root = Path(__file__).resolve().parents[1]
    canonical_doc = root / 'docs' / 'NEURON_PHASES.md'
    if canonical_hash and canonical_doc.exists():
        actual_doc = sha256(canonical_doc)
        if actual_doc != canonical_hash:
            failures.append(f"CANONICAL_DOC_MISMATCH:{actual_doc}!={canonical_hash}")
    if failures:
        print(json.dumps({"status": "fail", "failures": failures}, indent=2))
        return 1
    print(json.dumps({"status": "ok", "verified": list(artifacts.keys())}, indent=2))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gate', required=True, help='Path to gate_report_*.json')
    args = ap.parse_args()
    rc = verify(Path(args.gate))
    sys.exit(rc)

if __name__ == '__main__':  # pragma: no cover
    main()
