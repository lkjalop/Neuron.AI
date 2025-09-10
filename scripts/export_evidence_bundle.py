#!/usr/bin/env python3
"""Export compliance evidence bundle.

Collects:
 - audit/VULN_SNAPSHOTS_SIGNATURES.jsonl (if present)
 - audit/AUDIT_LOG.md, AUDIT_LOG_SIGNATURES.jsonl (if present)
 - audit/MANIFEST.json, audit/MANIFEST_CHAIN.jsonl (if present)
 - config/runtime_params.defaults.json (baseline parameters)
 - Latest vulnerability snapshot files referenced in signature chain (if accessible)

Produces bundle_manifest.json with entries:
  {
    "file": "relative/path",
    "sha256": "..."
  }
Optionally creates a .zip archive when --zip provided.
"""
from __future__ import annotations

import os, json, hashlib, argparse, zipfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / 'audit'
CONFIG = ROOT / 'config'

INCLUDE_FILES = [
    'VULN_SNAPSHOTS_SIGNATURES.jsonl',
    'AUDIT_LOG.md',
    'AUDIT_LOG_SIGNATURES.jsonl',
    'MANIFEST.json',
    'MANIFEST_CHAIN.jsonl',
]


def sha256_path(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def load_snapshot_paths(sig_file: Path) -> list[Path]:
    paths = []
    try:
        for line in sig_file.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            snap = rec.get('snapshot_file')
            if snap:
                sp = (AUDIT / snap) if not snap.startswith('/') else Path(snap)
                if sp.exists():
                    paths.append(sp)
    except Exception:
        pass
    return paths


def main():
    ap = argparse.ArgumentParser(description='Export evidence bundle')
    ap.add_argument('--output-dir', default='artifacts/evidence_bundle')
    ap.add_argument('--zip', action='store_true', help='Create zip archive')
    args = ap.parse_args()
    out_dir = ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"generated_at": time.time(), "files": []}
    # Collect static audit files
    for fname in INCLUDE_FILES:
        fp = AUDIT / fname
        if fp.exists():
            rel = fp.relative_to(ROOT).as_posix()
            manifest["files"].append({"file": rel, "sha256": sha256_path(fp)})
    # Runtime param defaults
    rp = CONFIG / 'runtime_params.defaults.json'
    if rp.exists():
        rel = rp.relative_to(ROOT).as_posix()
        manifest["files"].append({"file": rel, "sha256": sha256_path(rp)})
    # Snapshot files
    sig = AUDIT / 'VULN_SNAPSHOTS_SIGNATURES.jsonl'
    if sig.exists():
        for sp in load_snapshot_paths(sig):
            rel = sp.relative_to(ROOT).as_posix()
            manifest["files"].append({"file": rel, "sha256": sha256_path(sp)})
    manifest_path = out_dir / 'bundle_manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    archive_path = None
    if args.zip:
        archive_path = out_dir / 'evidence_bundle.zip'
        with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            # Include manifest
            z.write(manifest_path, arcname='bundle_manifest.json')
            for entry in manifest['files']:
                fp = ROOT / entry['file']
                if fp.exists():
                    z.write(fp, arcname=entry['file'])
    print(json.dumps({
        'status': 'ok',
        'manifest': manifest_path.as_posix(),
        'zip': archive_path.as_posix() if archive_path else None,
        'count': len(manifest['files']),
    }))

if __name__ == '__main__':
    main()
