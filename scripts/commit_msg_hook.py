"""Conventional commit message validator with scope enforcement.
Install by symlinking to .git/hooks/commit-msg or copying.

Valid types: feat, fix, docs, style, refactor, perf, test, build, chore, revert
Format: <type>(optional-scope)!?: <description>
Examples:
  feat(api): add governance endpoint
  fix: correct null dereference in fusion logic
Scope Enforcement:
  If files under src/core or scripts/ modified, scope is required and must be one of allowed scopes.
"""
from __future__ import annotations
import sys, re, pathlib, subprocess

ALLOWED = {"feat","fix","docs","style","refactor","perf","test","build","chore","revert"}
ALLOWED_SCOPES = {"core","api","ingest","detect","governance","scripts","docs","perf","security","ci"}
PATTERN = re.compile(r'^(?P<type>[a-z]+)(\((?P<scope>[^\)]+)\))?(!)?: .+')
IGNORES = ("Merge branch", "Merge pull request")


def _changed_files():
    try:
        proc = subprocess.run(["git","diff","--cached","--name-only"], capture_output=True, text=True, check=False)
        return [l.strip() for l in proc.stdout.splitlines() if l.strip()]
    except Exception:
        return []


def _needs_scope(files):
    for f in files:
        if f.startswith("src/core/") or f.startswith("scripts/"):
            return True
    return False


def main():
    if len(sys.argv) < 2:
        return 0
    path = pathlib.Path(sys.argv[1])
    msg_lines = path.read_text().splitlines()
    if not msg_lines:
        print('[commit-msg] Empty commit message')
        return 1
    first = msg_lines[0]
    if any(first.startswith(p) for p in IGNORES):
        return 0
    m = PATTERN.match(first)
    if not m:
        print('[commit-msg] Invalid conventional header')
        return 1
    ctype = m.group('type')
    scope = m.group('scope')
    if ctype not in ALLOWED:
        print(f"[commit-msg] Type {ctype} not allowed")
        return 1
    files = _changed_files()
    require_scope = _needs_scope(files)
    if require_scope and not scope:
        print('[commit-msg] Scope required for core/scripts changes. Allowed scopes:', ','.join(sorted(ALLOWED_SCOPES)))
        return 1
    if scope and scope not in ALLOWED_SCOPES:
        print(f"[commit-msg] Scope '{scope}' not in allowed set: {','.join(sorted(ALLOWED_SCOPES))}")
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
