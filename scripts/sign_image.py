"""Image signing scaffold using cosign.

Requires environment variables:
  COSIGN_PRIVATE_KEY (if key-mode) or OIDC provider in GitHub Actions (keyless).

Usage:
  python scripts/sign_image.py neuron-ai:prod
"""
from __future__ import annotations
import subprocess, sys, os

def have(exe: str) -> bool:
    from shutil import which
    return which(exe) is not None

def run(cmd: list[str]):
    print('[sign] $', ' '.join(cmd))
    rc = subprocess.call(cmd)
    if rc != 0:
        print('[sign] command failed rc', rc)
        return rc
    return 0

def main():
    if len(sys.argv) < 2:
        print('usage: sign_image.py <image-ref>')
        return 1
    image = sys.argv[1]
    if not have('cosign'):
        print('[sign] cosign not installed, skip')
        return 0
    key = os.getenv('COSIGN_PRIVATE_KEY')
    if key:
        # key-based signing
        run(['cosign', 'sign', '--key', 'env://COSIGN_PRIVATE_KEY', image])
    else:
        # keyless signing (GitHub OIDC environment) if supported
        run(['cosign', 'sign', image])
    print('[sign] done')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
