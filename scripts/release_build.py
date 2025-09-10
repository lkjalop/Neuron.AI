"""Automate release process.

Steps:
 1. Validate working tree clean (optional skip via --no-git-check)
 2. Run security baseline (fail fast if issues)
 3. Bump version (patch/minor/major) in core/version.py
 4. Regenerate OpenAPI (if export script present)
 5. Generate MANIFEST (artifacts + hashes) -> artifacts/release_manifest.json
 6. Append CHANGELOG.md entry skeleton if not already present for new version
 7. Commit + tag (optional with --git) and print next commands

Usage:
  python scripts/release_build.py --bump patch --git
"""
from __future__ import annotations
import argparse, pathlib, re, subprocess, sys, hashlib, json, datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / 'core' / 'version.py'
CHANGELOG = ROOT / 'CHANGELOG.md'
ARTIFACTS = ROOT / 'artifacts'
MANIFEST_OUT = ARTIFACTS / 'release_manifest.json'
SECURITY_SCRIPT = ROOT / 'scripts' / 'security_baseline.py'
OPENAPI_SCRIPT = ROOT / 'docs' / 'export_openapi.py'

SEMVER_RE = re.compile(r'__version__\s*=\s*"(\d+)\.(\d+)\.(\d+)"')
GEN_CHANGELOG = ROOT / 'scripts' / 'gen_changelog_section.py'

def read_version() -> tuple[int,int,int]:
    text = VERSION_FILE.read_text()
    m = SEMVER_RE.search(text)
    if not m:
        raise SystemExit('Version marker not found')
    return tuple(int(x) for x in m.groups())  # type: ignore

def write_version(v: tuple[int,int,int]):
    major, minor, patch = v
    text = VERSION_FILE.read_text()
    new_text = SEMVER_RE.sub(f'__version__ = "{major}.{minor}.{patch}"', text)
    VERSION_FILE.write_text(new_text)


def bump(kind: str, v: tuple[int,int,int]) -> tuple[int,int,int]:
    major, minor, patch = v
    if kind == 'patch':
        patch += 1
    elif kind == 'minor':
        minor += 1; patch = 0
    elif kind == 'major':
        major += 1; minor = 0; patch = 0
    else:
        raise SystemExit('Invalid bump kind')
    return major, minor, patch


def run(cmd: list[str], check=True):
    print('[release] $', ' '.join(cmd))
    rc = subprocess.call(cmd)
    if check and rc != 0:
        raise SystemExit(f'Command failed rc={rc}')
    return rc


def git_clean() -> bool:
    rc = subprocess.call(['git', 'diff-index', '--quiet', 'HEAD', '--'])
    return rc == 0


def run_security():
    if SECURITY_SCRIPT.exists():
        run([sys.executable, str(SECURITY_SCRIPT)])
    else:
        print('[release] Security script missing (skip)')


def export_openapi():
    if OPENAPI_SCRIPT.exists():
        run([sys.executable, str(OPENAPI_SCRIPT)])
    else:
        print('[release] OpenAPI export script missing (skip)')


def hash_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def build_manifest():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    entries = []
    for path in ARTIFACTS.rglob('*'):
        if path.is_file():
            rel = path.relative_to(ROOT).as_posix()
            entries.append({
                'path': rel,
                'sha256': hash_file(path),
                'size': path.stat().st_size
            })
    manifest = {
        'generated': datetime.datetime.utcnow().isoformat() + 'Z',
        'entries': entries
    }
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2))
    print(f'[release] Wrote manifest {MANIFEST_OUT}')


def ensure_changelog(new_version: str, auto: bool=False):
    text = CHANGELOG.read_text() if CHANGELOG.exists() else ''
    if f'## {new_version}' in text:
        print('[release] Changelog entry exists (skip append)')
        return
    if auto and GEN_CHANGELOG.exists():
        try:
            section = subprocess.check_output([sys.executable, str(GEN_CHANGELOG)], text=True)
        except Exception as e:
            print(f'[release] Auto changelog generation failed: {e}')
            section = '- TBD: Describe changes.'
    else:
        section = '- TBD: Describe changes.'
    header = f"\n\n## {new_version} - {datetime.date.today().isoformat()}\n\n{section.strip()}\n"
    if text.strip():
        CHANGELOG.write_text(text.rstrip() + header)
    else:
        CHANGELOG.write_text(f"## {new_version} - {datetime.date.today().isoformat()}\n\n- Initial entry.\n")
    print('[release] Appended CHANGELOG entry skeleton')


def git_commit_tag(new_version: str):
    run(['git', 'add', str(VERSION_FILE), str(CHANGELOG), str(MANIFEST_OUT)], check=True)
    run(['git', 'commit', '-m', f'release: v{new_version}'], check=True)
    run(['git', 'tag', f'v{new_version}'], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bump', choices=['patch','minor','major'], default='patch')
    ap.add_argument('--git', action='store_true', help='Commit and tag automatically')
    ap.add_argument('--auto-changelog', action='store_true', help='Generate changelog section from conventional commits')
    ap.add_argument('--no-git-check', action='store_true', help='Skip clean working tree check')
    args = ap.parse_args()

    if not args.no_git_check and not git_clean():
        print('[release] Working tree not clean, abort. Use --no-git-check to override.')
        return 1

    cur = read_version()
    new = bump(args.bump, cur)
    new_version = '.'.join(map(str,new))
    print(f'[release] Bumping version {cur} -> {new_version}')

    run_security()
    export_openapi()

    write_version(new)
    build_manifest()
    ensure_changelog(new_version, auto=args.auto_changelog)

    if args.git:
        git_commit_tag(new_version)
        print(f'[release] Created tag v{new_version}')

    print(f'[release] SUCCESS new version {new_version}')
    print('Next steps:')
    print(f'  git push origin HEAD && git push origin v{new_version}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
