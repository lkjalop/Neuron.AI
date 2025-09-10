"""Create a governed savepoint snapshot.

Steps performed:
1. Compute SHA256 of docs/NEURON_PHASES.md and write/update audit/CANONICAL_DOC_HASH
2. Optional: capture runtime param snapshot stub (placeholder until param store formalized)
3. Append structured entry to audit/AUDIT_LOG.md with hashes
4. Emit git commands user should run to commit + tag (we avoid running git directly here for safety)

Idempotent: running multiple times updates hash file and appends new log entry.
"""
from __future__ import annotations
import hashlib, json, os, time, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CANONICAL_DOC = ROOT / "docs" / "NEURON_PHASES.md"
CANONICAL_HASH_FILE = ROOT / "audit" / "CANONICAL_DOC_HASH"
AUDIT_LOG = ROOT / "audit" / "AUDIT_LOG.md"
PARAM_SNAPSHOT_DIR = ROOT / "audit"


def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def write_hash(h: str) -> None:
    CANONICAL_HASH_FILE.write_text(h + "\n", encoding="utf-8")


def create_param_snapshot() -> pathlib.Path:
    # Placeholder – extend to pull from central runtime param store
    snapshot = {
        "timestamp": time.time(),
        "note": "Placeholder param snapshot; integrate runtime_params export later",
        "env_flags": {k: v for k, v in os.environ.items() if k.startswith("NEURON_") or k.startswith("ENABLE_")},
    }
    path = PARAM_SNAPSHOT_DIR / f"param_snapshot_{int(time.time())}.json"
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    return path


def append_audit_entry(doc_hash: str, param_path: pathlib.Path) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    entry = [
        "\n### Savepoint (Automated Script)",
        f"Date: {ts} UTC",
        f"Canonical Doc Hash: `{doc_hash}`",
        f"Param Snapshot: `{param_path.name}`",
        "Action: Pre-pivot snapshot (detector orchestrator + hybrid path)",
        "---",
    ]
    # Ensure log exists
    if not AUDIT_LOG.exists():
        AUDIT_LOG.write_text("# Audit Log\n", encoding="utf-8")
    with AUDIT_LOG.open('a', encoding='utf-8') as f:
        f.write("\n".join(entry) + "\n")


def main():
    if not CANONICAL_DOC.exists():
        print(f"ERROR: canonical doc not found at {CANONICAL_DOC}", file=sys.stderr)
        sys.exit(1)
    doc_hash = sha256_file(CANONICAL_DOC)
    write_hash(doc_hash)
    param_snapshot = create_param_snapshot()
    append_audit_entry(doc_hash, param_snapshot)
    tag_suggest = time.strftime("savepoint-%Y%m%d-%H%M%S")
    print("Savepoint created.")
    print(f"Canonical hash: {doc_hash}")
    print(f"Param snapshot: {param_snapshot.name}")
    print("Run the following to persist and tag:")
    print()
    print("git add audit/CANONICAL_DOC_HASH audit/AUDIT_LOG.md audit/" + param_snapshot.name)
    print(f"git commit -m 'Savepoint: pre-pivot {tag_suggest}'")
    print(f"git tag -a {tag_suggest} -m 'Automated savepoint'")


if __name__ == "__main__":
    main()
