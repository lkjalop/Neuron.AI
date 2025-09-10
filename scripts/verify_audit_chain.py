"""Audit chain verification utility.

Traverses the primary audit log `audit/param_changes.log` and any rotated
files (`audit/param_changes.log.*`), verifying the integrity of the chained
hash sequence. Each line is expected to be a JSON object:
  {"prev": <hex>, "rec": {...}}

The current hash for a line is sha256 of the raw JSON line (without trailing newline).
The `prev` field of each entry (except the first) must match the hash of the
previous line. The latest hash should match the contents of `audit/param_changes.head`.

Exit Codes:
  0 - Success, chain valid
  1 - Structural error (file unreadable / malformed JSON)
  2 - Hash mismatch / integrity failure
  3 - Head file mismatch with computed last hash
  4 - No entries found (empty chain considered failure for governance)
"""
from __future__ import annotations

import pathlib, sys, json, hashlib, glob
from typing import List

AUDIT_FILE = pathlib.Path("audit/param_changes.log")
HEAD_FILE = pathlib.Path("audit/param_changes.head")

def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def iter_audit_files() -> List[pathlib.Path]:
    base = str(AUDIT_FILE)
    rotated = sorted(glob.glob(base + ".*"))  # chronological by timestamp suffix assumption
    files = [pathlib.Path(p) for p in rotated]
    if AUDIT_FILE.exists():
        files.append(AUDIT_FILE)
    return files

def verify() -> int:
    files = iter_audit_files()
    if not files:
        print("[ERROR] No audit log files found", file=sys.stderr)
        return 4
    prev_hash = "0" * 64
    last_hash = None
    entries = 0
    for f in files:
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except Exception as e:  # noqa: BLE001
            print(f"[ERROR] Unable to read {f}: {e}", file=sys.stderr)
            return 1
        for line in lines:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception as e:  # noqa: BLE001
                print(f"[ERROR] Malformed JSON in {f}: {e}", file=sys.stderr)
                return 1
            if "prev" not in obj or "rec" not in obj:
                # Legacy un-chained record prior to hash chain rollout; skip but do not break verification
                # Maintain previous prev_hash (do not advance chain) so first chained entry still expects zeros or prior hash
                continue
            if obj["prev"] != prev_hash:
                print(f"[ERROR] Hash chain mismatch: expected prev={prev_hash} got={obj['prev']}", file=sys.stderr)
                return 2
            # compute current hash
            curr_hash = sha256_str(line)
            prev_hash = curr_hash
            last_hash = curr_hash
            entries += 1
    if entries == 0:
        print("[ERROR] No audit entries present", file=sys.stderr)
        return 4
    # Head file validation
    if HEAD_FILE.exists():
        try:
            head_val = HEAD_FILE.read_text(encoding="utf-8").strip()
            if head_val != last_hash:
                print(f"[ERROR] Head hash mismatch: head={head_val} computed={last_hash}", file=sys.stderr)
                return 3
        except Exception as e:  # noqa: BLE001
            print(f"[ERROR] Unable to read head file: {e}", file=sys.stderr)
            return 1
    print(f"[OK] Audit chain verified: {entries} entries across {len(files)} file(s). Last hash={last_hash}")
    return 0

if __name__ == "__main__":  # pragma: no cover
    sys.exit(verify())
