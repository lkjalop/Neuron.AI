"""Lightweight secret pattern scanner.

Patterns flagged (heuristic):
 - Potential JWT: eyJ[a-zA-Z0-9_-]{10,}
 - Neon password token prefix: npg_
 - 64+ hex strings outside known hash files
Exclusions: audit/*.log, *.pyc, artifacts/*

Exit codes: 0 none, 1 potential matches.
"""
from __future__ import annotations
import re, pathlib, sys

ROOT = pathlib.Path('.')
JWT_RE = re.compile(r"eyJ[a-zA-Z0-9_-]{10,}")
HEX64_RE = re.compile(r"\b[a-fA-F0-9]{64,}\b")
NPG_RE = re.compile(r"npg_[A-Za-z0-9]{8,}")

EXCLUDE_DIRS = {'.git', '__pycache__', 'artifacts', '.venv'}
EXCLUDE_FILES = {'.env', '.env.example'}

suspicious: list[tuple[str, str]] = []

for path in ROOT.rglob('*'):
    if path.is_dir():
        if path.name in EXCLUDE_DIRS:
            continue
        else:
            continue
for path in ROOT.rglob('*'):
    if path.is_dir():
        continue
    if path.name in EXCLUDE_FILES:
        continue
    if any(part in EXCLUDE_DIRS for part in path.parts):
        continue
    if path.suffix in {'.pyc', '.png', '.jpg', '.jpeg', '.gif'}:
        continue
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        continue
    # Basic heuristics
    if JWT_RE.search(text):
        suspicious.append((str(path), 'JWT-like token'))
    if NPG_RE.search(text):
        suspicious.append((str(path), 'Neon token pattern'))
    if HEX64_RE.search(text) and 'AUDIT_LOG.md' not in str(path):
        suspicious.append((str(path), 'Long hex sequence'))

if suspicious:
    for f, why in suspicious[:200]:
        print(f"[POTENTIAL] {why}: {f}")
    print(f"Total potential matches: {len(suspicious)}")
    sys.exit(1)
else:
    print("No obvious secret patterns detected.")
    sys.exit(0)
