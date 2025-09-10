"""Verify a synthetic dataset JSONL against its manifest.

Checks:
  - Line count matches manifest event_count
  - Recomputed Merkle root (concat of per-line sha256 hashes) matches manifest events_merkle_root
Usage:
  python scripts/verify_dataset.py --events events.jsonl --manifest artifacts/dataset/events.manifest.json
"""
from __future__ import annotations
import argparse, json, hashlib, sys
from pathlib import Path

def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()

def compute_root(lines):
    hashes = [sha256_text(l.rstrip('\n')) for l in lines]
    return sha256_text("".join(hashes)), len(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--events', type=Path, required=True)
    ap.add_argument('--manifest', type=Path, required=True)
    args = ap.parse_args()
    lines = args.events.read_text(encoding='utf-8').splitlines()
    root, count = compute_root(lines)
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    m_count = manifest.get('event_count')
    m_root = manifest.get('events_merkle_root')
    ok = True
    if count != m_count:
        print(f'COUNT MISMATCH: file={count} manifest={m_count}')
        ok = False
    if root != m_root:
        print(f'HASH MISMATCH: file={root} manifest={m_root}')
        ok = False
    if ok:
        print(f'OK dataset verified: count={count}')
    else:
        sys.exit(1)

if __name__ == '__main__':  # pragma: no cover
    main()
