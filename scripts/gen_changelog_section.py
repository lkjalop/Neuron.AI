"""Generate changelog section from conventional commits.

Rules:
- Collect commits from last tag (git describe --tags --abbrev=0) to HEAD.
- Parse conventional commit types: feat, fix, perf, docs, refactor, chore, test, build.
- Group by type, output markdown bullets.
- Ignore merge commits unless they contain a conventional header.

Usage:
  python scripts/gen_changelog_section.py > section.md
"""
from __future__ import annotations
import subprocess, re, sys

TYPES_ORDER = ["feat","fix","perf","refactor","docs","test","build","chore"]
HEADER_RE = re.compile(r'^(?P<type>feat|fix|perf|refactor|docs|test|build|chore)(\([^\)]+\))?(!)?:\s+(?P<msg>.+)')

def run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()

def last_tag() -> str | None:
    try:
        return run(['git','describe','--tags','--abbrev=0'])
    except subprocess.CalledProcessError:
        return None

def collect_commits(since_tag: str | None) -> list[str]:
    rev_range = f'{since_tag}..HEAD' if since_tag else 'HEAD'
    try:
        out = run(['git','log','--pretty=%s','--no-merges',rev_range])
    except subprocess.CalledProcessError:
        return []
    return [l for l in out.splitlines() if l.strip()]

def main():
    tag = last_tag()
    commits = collect_commits(tag)
    groups: dict[str,list[str]] = {t: [] for t in TYPES_ORDER}
    for c in commits:
        m = HEADER_RE.match(c)
        if not m:
            continue
        t = m.group('type')
        msg = m.group('msg')
        # strip scope breaking changes annotation '!' already captured
        groups[t].append(msg.strip())
    printed = False
    for t in TYPES_ORDER:
        items = groups[t]
        if not items:
            continue
        printed = True
        print(f'### {t}')
        for it in items:
            print(f'- {it}')
        print()
    if not printed:
        print('- Minor internal changes')

if __name__ == '__main__':
    main()
