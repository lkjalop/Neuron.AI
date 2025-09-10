#!/usr/bin/env python3
"""Finalize A16 hash placeholders.

Steps:
 1. Compute SHA256 for defined A16 artifact files.
 2. Append an "A16 Hash Resolution Addendum" section to audit/AUDIT_LOG.md (append-only; do not edit prior lines).
 3. Update audit/MANIFEST.json by:
    - Recording previous manifest hash (sha256 of prior file content) into `previous_manifest_hash`.
    - Adding any missing artifact file hashes into the `files` map (idempotent: skips if already present with same hash).
    - Refreshing `timestamp`.
 4. Append the new manifest object as a JSON line to audit/MANIFEST_CHAIN.jsonl to extend the chain.

Idempotency:
 - If the addendum already exists (detected by heading), script exits without changes.
 - Manifest update only occurs if addendum not yet appended.

Usage:
  python scripts/finalize_audit_hashes.py
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
AUDIT_LOG = ROOT / "audit" / "AUDIT_LOG.md"
MANIFEST = ROOT / "audit" / "MANIFEST.json"
CHAIN = ROOT / "audit" / "MANIFEST_CHAIN.jsonl"

# Ordered list to preserve presentation order matching A16 placeholder line
A16_ARTIFACTS = [
    "src/core/detect/isolation_forest.py",  # isolation_forest.py
    "src/config/runtime_params.py",          # runtime_params.py
    "src/core/metrics.py",                  # metrics.py
    "src/core/agent/insights.py",           # insights.py
    "scripts/rag_ingest.py",                # rag_ingest.py
    "src/core/main.py",                     # (included in Artifacts list though not in placeholders line order)
    "tests/test_integration_multi_detector_insights.py",  # test_integration_multi_detector_insights.py
    "tests/test_rag_ingest.py",             # test_rag_ingest.py
]

ADDENDUM_HEADING = "### A16 Hash Resolution Addendum"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def load_manifest() -> dict:
    with MANIFEST.open('r', encoding='utf-8') as f:
        return json.load(f)


def write_manifest(obj: dict) -> None:
    with MANIFEST.open('w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write('\n')


def append_chain_entry(obj: dict) -> None:
    # Compact representation (similar to initial file style) isn't mandatory; keep pretty for readability.
    with CHAIN.open('a', encoding='utf-8') as f:
        f.write(json.dumps(obj, sort_keys=True))
        f.write('\n')


def append_addendum(hashes: list[tuple[str, str]]) -> None:
    ts = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    lines = ["", f"{ADDENDUM_HEADING} ({ts})", "ResolvedHashes:"]
    # Mirror earlier formatting: key=value pairs with tabs for readability
    for rel_path, digest in hashes:
        key = Path(rel_path).name  # Use filename key matching placeholder style
        lines.append(f"\t{key}={digest}")
    lines.append("Integrity: All hashes are reproducible; discrepancies imply tamper or regeneration without audit entry.")
    with AUDIT_LOG.open('a', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def main():
    if ADDENDUM_HEADING in AUDIT_LOG.read_text(encoding='utf-8'):
        print("Addendum already present; nothing to do.")
        return

    # Validate artifact presence & compute hashes
    resolved: list[tuple[str, str]] = []
    missing: list[str] = []
    for rel in A16_ARTIFACTS:
        p = ROOT / rel
        if not p.exists():
            missing.append(rel)
            continue
        resolved.append((rel.replace('\\', '/'), sha256_file(p)))

    if missing:
        raise SystemExit(f"Missing expected artifact files: {missing}")

    # Append addendum first (audit order: evidence before manifest mutation is acceptable; both in same commit)
    append_addendum(resolved)

    # Update manifest
    manifest_raw = MANIFEST.read_text(encoding='utf-8')
    prev_hash = hashlib.sha256(manifest_raw.encode('utf-8')).hexdigest()
    manifest = json.loads(manifest_raw)

    files_map: dict = manifest.get('files', {})
    # Insert / verify each artifact
    for rel, digest in resolved:
        existing = files_map.get(rel)
        if existing and existing != digest:
            # If content changed after placeholder creation, we still capture new hash; historical diff must be referenced in new audit entry if intentional.
            print(f"Warning: existing manifest hash for {rel} differs; updating to new digest.")
        files_map[rel] = digest

    manifest['files'] = files_map
    manifest['previous_manifest_hash'] = prev_hash
    manifest['timestamp'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    write_manifest(manifest)
    append_chain_entry(manifest)

    print("A16 hash finalization complete. Added addendum and updated manifest.")
    for rel, digest in resolved:
        print(f"{rel}: {digest}")


if __name__ == '__main__':
    main()
