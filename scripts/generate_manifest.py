"""Generate a manifest (simple hash chain) for tracked files.
Run this after meaningful changes. Append hash reference to audit log manually.
"""
from __future__ import annotations
import hashlib, json, os, pathlib, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
TRACK_EXT = {".py", ".md", ".txt", ".yaml", ".yml", ".json", ".toml"}
IGNORE_DIRS = {"archives", "__pycache__", ".git", ".venv"}
MANIFEST_PATH = ROOT / "audit" / "MANIFEST.json"
CHAIN_PATH = ROOT / "audit" / "MANIFEST_CHAIN.jsonl"

def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_files():
    files = []
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix in TRACK_EXT and not any(d in p.parts for d in IGNORE_DIRS):
            files.append(p)
    return files


def build_manifest():
    prev_hash = None
    if MANIFEST_PATH.exists():
        prev_hash = sha256_file(MANIFEST_PATH)
    files = collect_files()
    manifest = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "previous_manifest_hash": prev_hash,
        "files": {},
    }
    for f in sorted(files):
        rel = f.relative_to(ROOT).as_posix()
        manifest["files"][rel] = sha256_file(f)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with open(CHAIN_PATH, "a", encoding="utf-8") as chain:
        chain.write(json.dumps(manifest) + "\n")
    print(f"Manifest generated with {len(manifest['files'])} files.")

if __name__ == "__main__":
    build_manifest()
