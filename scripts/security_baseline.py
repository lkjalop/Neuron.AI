"""Run security & supply chain baseline checks.

Steps:
 1. Ruff lint
 2. Bandit scan
 3. pip-audit (requirements)
 4. CycloneDX SBOM generation
 5. (Placeholder) detect-secrets scan

Exit non-zero if high severity issues detected (simplified heuristic).
"""
from __future__ import annotations
import subprocess, sys, json, pathlib, shutil, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
ART = ROOT / 'artifacts' / 'security'
ART.mkdir(parents=True, exist_ok=True)


def run(cmd: list[str], ignore_error: bool = False) -> int:
    print(f"[security] RUN: {' '.join(cmd)}")
    rc = subprocess.call(cmd)
    if rc != 0 and not ignore_error:
        print(f"[security] Command failed rc={rc}")
    return rc

def have(exe: str) -> bool:
    return shutil.which(exe) is not None

issues = 0

# 1. Ruff
if have('ruff'):
    issues += run(['ruff', 'check', 'src', 'tests'])
else:
    print('[security] Ruff not installed (skip)')

# 2. Bandit
if have('bandit'):
    bandit_out = ART / 'bandit.json'
    rc = run(['bandit', '-q', '-r', 'src', '-f', 'json', '-o', str(bandit_out)], ignore_error=True)
    if bandit_out.exists():
        data = json.loads(bandit_out.read_text())
        high = [i for i in data.get('results', []) if i.get('issue_severity') == 'HIGH']
        if high:
            print(f"[security] Bandit HIGH findings: {len(high)}")
            issues += len(high)
else:
    print('[security] Bandit not installed (skip)')

# 3. pip-audit (JSON output)
if have('pip-audit'):
    pip_audit_out = ART / 'pip_audit.json'
    rc = run(['pip-audit', '-r', 'requirements.txt', '-f', 'json', '-o', str(pip_audit_out)], ignore_error=True)
    if pip_audit_out.exists():
        data = json.loads(pip_audit_out.read_text())
        vulns = 0
        for pkg in data:
            for v in pkg.get('vulns', []):
                sev = v.get('severity', 'UNKNOWN')
                if sev in {'HIGH','CRITICAL'}:
                    vulns += 1
        if vulns:
            print(f"[security] High/Critical dependency vulns: {vulns}")
            issues += vulns
else:
    print('[security] pip-audit not installed (skip)')

# 4. CycloneDX (attempt)
if have('cyclonedx-py'):
    sbom_path = ART / 'sbom.json'
    run(['cyclonedx-py', 'environment', '--format', 'json', '--outfile', str(sbom_path)], ignore_error=True)
else:
    print('[security] cyclonedx-py not installed (skip)')

# 5. detect-secrets (baseline compare)
if have('detect-secrets'):
    repo_baseline = ROOT / '.secrets.baseline'
    if repo_baseline.exists():
        # Scan current tree and compare with baseline
        tmp_scan = tempfile.NamedTemporaryFile(delete=False, suffix='.baseline')
        tmp_scan.close()
        run(['detect-secrets', 'scan', '--all-files', '--exclude-files', '(\.venv|venv|dist)', '--baseline', tmp_scan.name], ignore_error=True)
        try:
            new_data = json.loads(pathlib.Path(tmp_scan.name).read_text())
            old_data = json.loads(repo_baseline.read_text())
            new_results = new_data.get('results', {})
            if new_results:
                print(f"[security] Potential secrets detected: {len(new_results)} (compare with baseline)")
                issues += len(new_results)
            else:
                print('[security] No new secrets detected')
        finally:
            pathlib.Path(tmp_scan.name).unlink(missing_ok=True)
    else:
        print('[security] No .secrets.baseline present (initializing)')
        run(['detect-secrets', 'scan', '--all-files', '--exclude-files', '(\.venv|venv|dist)', '--baseline', str(repo_baseline)], ignore_error=True)
else:
    print('[security] detect-secrets not installed (skip)')

if issues:
    print(f"[security] FAIL total issues={issues}")
    sys.exit(1)
print('[security] PASS baseline clean (no high severity issues)')
