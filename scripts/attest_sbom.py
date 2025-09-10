"""Create provenance attestation for CycloneDX SBOM using cosign."""
from __future__ import annotations
import pathlib, sys, subprocess, os

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEC_DIR = ROOT / 'artifacts' / 'security'
SBOM = SEC_DIR / 'sbom.json'

def run(cmd: list[str]):
    print('[attest] $', ' '.join(cmd))
    rc = subprocess.call(cmd)
    if rc != 0:
        print('[attest] command failed rc', rc)
    return rc

def main():
    if not SBOM.exists():
        print('[attest] SBOM not found at', SBOM)
        return 1
    if not shutil.which('cosign'):
        print('[attest] cosign not installed, skip')
        return 0
    image = sys.argv[1] if len(sys.argv) > 1 else None
    if not image:
        print('usage: attest_sbom.py <image-ref>')
        return 1
    # cosign attest --predicate sbom.json --type cyclonedx <image>
    rc = run(['cosign','attest','--predicate', str(SBOM), '--type','cyclonedx', image])
    return rc

if __name__ == '__main__':
    import shutil
    raise SystemExit(main())
