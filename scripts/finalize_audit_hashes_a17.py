#!/usr/bin/env python3
"""Finalize A17 hash placeholders.

Steps:
 1. Compute SHA256 for defined A17 artifact files (those listed in A17 PendingHashes section).
 2. Append an "A17 Hash Resolution Addendum" section to audit/AUDIT_LOG.md (append-only; do not edit prior lines).
 3. Update audit/MANIFEST.json:
    - Record previous manifest hash into `previous_manifest_hash`.
    - Insert / update each artifact hash in the manifest files map.
    - Refresh timestamp.
 4. Append updated manifest JSON as a new line in audit/MANIFEST_CHAIN.jsonl.

Idempotency:
 - If the addendum heading already exists, exit without modifying anything.
 - Missing artifact files cause an error (integrity expectation).

Usage:
  python scripts/finalize_audit_hashes_a17.py
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
AUDIT_LOG = ROOT / "audit" / "AUDIT_LOG.md"
MANIFEST = ROOT / "audit" / "MANIFEST.json"
CHAIN = ROOT / "audit" / "MANIFEST_CHAIN.jsonl"

A17_ARTIFACTS = [
    "src/config/flags.py",               # flags.py
    "src/config/runtime_params.py",      # runtime_params.py
    "scripts/rag_ingest.py",             # rag_ingest.py
    "src/core/retrieval/interface.py",   # interface.py
    "tests/test_rag_multi_doc.py",       # test_rag_multi_doc.py
]

ADDENDUM_HEADING = "### A17 Hash Resolution Addendum"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def append_addendum(hashes: list[tuple[str, str]]) -> None:
    ts = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    lines = ["", f"{ADDENDUM_HEADING} ({ts})", "ResolvedHashes:"]
    for rel, digest in hashes:
        key = Path(rel).name
        lines.append(f"\t{key}={digest}")
    lines.append("Integrity: All hashes are reproducible; discrepancies imply tamper or regeneration without audit entry.")
    with AUDIT_LOG.open('a', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def main():
    if ADDENDUM_HEADING in AUDIT_LOG.read_text(encoding='utf-8'):
        print("A17 addendum already present; nothing to do.")
        return

    resolved: list[tuple[str, str]] = []
    missing: list[str] = []
    for rel in A17_ARTIFACTS:
        p = ROOT / rel
        if not p.exists():
            missing.append(rel)
            continue
        resolved.append((rel.replace('\\', '/'), sha256_file(p)))

    if missing:
        raise SystemExit(f"Missing expected A17 artifact files: {missing}")

    # Append addendum first
    append_addendum(resolved)

    # Update manifest
    manifest_raw = MANIFEST.read_text(encoding='utf-8')
    prev_hash = hashlib.sha256(manifest_raw.encode('utf-8')).hexdigest()
    manifest = json.loads(manifest_raw)

    files_map: dict = manifest.get('files', {})
    for rel, digest in resolved:
        existing = files_map.get(rel)
        if existing and existing != digest:
            print(f"Warning: existing manifest hash for {rel} differs; updating.")
        files_map[rel] = digest

    manifest['files'] = files_map
    manifest['previous_manifest_hash'] = prev_hash
    manifest['timestamp'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    with MANIFEST.open('w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write('\n')

    with CHAIN.open('a', encoding='utf-8') as f:
        f.write(json.dumps(manifest, sort_keys=True) + '\n')

    print("A17 hash finalization complete.")
    for rel, digest in resolved:
        print(f"{rel}: {digest}")

if __name__ == '__main__':
    main()
