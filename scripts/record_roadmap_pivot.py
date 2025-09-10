"""Append roadmap pivot audit entry with signed hash chain continuation."""
import hashlib
import time
from pathlib import Path

AUDIT_LOG = Path("audit/param_changes.log")
HEAD_FILE = Path("audit/param_changes.head")


def get_last_hash():
    if HEAD_FILE.exists():
        return HEAD_FILE.read_text().strip()
    return ""

def append_audit_entry(message: str, actor: str = "system"):
    ts = int(time.time())
    last_hash = get_last_hash()
    entry = f"{ts}|{actor}|{message}|{last_hash}"
    new_hash = hashlib.sha256(entry.encode("utf-8")).hexdigest()
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")
    HEAD_FILE.write_text(new_hash)
    print(f"Appended audit entry. New chain head: {new_hash}")

if __name__ == "__main__":
    import sys
    msg = sys.argv[1] if len(sys.argv) > 1 else "Roadmap pivot: batch update"
    append_audit_entry(msg)
