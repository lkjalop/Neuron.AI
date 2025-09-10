"""Update Canonical Hash Script

Computes a rolling hash of key documentation and parameter files then updates
AUDIT canonical doc hash file for chain-of-custody.
"""
from __future__ import annotations

import hashlib, pathlib, json, time

TARGETS = [
    "README.md",
    "requirements.txt",
    "config/runtime_params.defaults.json",
]
HASH_PATH = pathlib.Path("audit/CANONICAL_DOC_HASH")


def compute_hash() -> str:
    h = hashlib.sha256()
    for rel in TARGETS:
        p = pathlib.Path(rel)
        if not p.exists():
            continue
        h.update(rel.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def main():
    digest = compute_hash()
    HASH_PATH.write_text(digest + "\n", encoding="utf-8")
    manifest = {
        "ts": time.time(),
        "hash": digest,
        "targets": TARGETS,
    }
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
