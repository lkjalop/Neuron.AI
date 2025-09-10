#!/usr/bin/env python3
"""Verify vulnerability snapshot signature chain.

Reads audit/VULN_SNAPSHOTS_SIGNATURES.jsonl where each line is a JSON object:
  {
    "snapshot_file": "path/to/snapshot.json",
    "snapshot_sha256": "...",   # expected digest of snapshot file contents
    "chain_prev": "...",         # previous link hash (hex) or null for first
    "chain_hash": "...",         # this record's computed chain hash (H(prev||snapshot_sha256))
    "sig_hmac": "...",           # optional hex HMAC over chain_hash
    "sig_ed25519": "..."         # optional base64 signature over chain_hash
  }

Verification steps:
 1. Recompute SHA256 of each referenced snapshot file.
 2. Recompute chain hash: sha256(prev_chain_hash_bytes + snapshot_sha256_bytes).
 3. If environment variables NEURON_SNAPSHOT_HMAC_KEY is set and sig_hmac present, verify.
 4. If ed25519 public key file provided via --ed25519-pub path and sig_ed25519 present, verify.
 5. Emit JSON summary to stdout and exit non-zero on any failure.

Exit codes:
 0 success
 1 structural / IO error
 2 verification failure (digest mismatch, signature failure, chain break)
"""
from __future__ import annotations

import argparse, os, sys, json, hashlib, base64
from typing import List, Dict, Any, Optional

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey  # type: ignore
    from cryptography.hazmat.primitives import serialization  # type: ignore
    _HAS_CRYPTO = True
except Exception:
    _HAS_CRYPTO = False


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def hmac_sha256(key: bytes, msg: bytes) -> str:
    import hmac
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def load_ed25519_pub(path: str):
    with open(path, 'rb') as f:
        data = f.read()
    return Ed25519PublicKey.from_public_bytes(data)


def verify_chain(lines: List[str], ed25519_pub: Optional[Any], hmac_key: Optional[bytes]) -> Dict[str, Any]:
    results = []
    prev_chain = None
    ok = True
    for idx, raw in enumerate(lines):
        try:
            rec = json.loads(raw)
        except Exception as e:
            results.append({"index": idx, "error": f"json_parse: {e}"})
            ok = False
            break
        snapshot_file = rec.get('snapshot_file')
        expected_digest = rec.get('snapshot_sha256')
        chain_prev = rec.get('chain_prev')
        chain_hash = rec.get('chain_hash')
        sig_hmac = rec.get('sig_hmac')
        sig_ed = rec.get('sig_ed25519')
        record_ok = True
        errors = []
        if (prev_chain is None and chain_prev not in (None, "")) or (prev_chain is not None and chain_prev != prev_chain):
            record_ok = False
            errors.append('chain_prev_mismatch')
        # Snapshot digest
        try:
            actual_digest = sha256_file(snapshot_file)
            if expected_digest and expected_digest != actual_digest:
                record_ok = False
                errors.append('snapshot_sha256_mismatch')
        except Exception as e:
            record_ok = False
            errors.append(f'snapshot_read_error:{e}')
            actual_digest = None
        # Recompute chain hash
        prev_bytes = bytes.fromhex(prev_chain) if prev_chain else b''
        snap_bytes = bytes.fromhex(expected_digest) if expected_digest else b''
        recomputed = hashlib.sha256(prev_bytes + snap_bytes).hexdigest()
        if chain_hash != recomputed:
            record_ok = False
            errors.append('chain_hash_mismatch')
        # HMAC verification
        if sig_hmac and hmac_key:
            recomputed_hmac = hmac_sha256(hmac_key, bytes.fromhex(chain_hash))
            if recomputed_hmac != sig_hmac:
                record_ok = False
                errors.append('hmac_signature_invalid')
        # Ed25519 verification
        if sig_ed and ed25519_pub:
            if not _HAS_CRYPTO:
                record_ok = False
                errors.append('ed25519_module_missing')
            else:
                try:
                    ed25519_pub.verify(base64.b64decode(sig_ed), bytes.fromhex(chain_hash))
                except Exception:
                    record_ok = False
                    errors.append('ed25519_signature_invalid')
        results.append({
            'index': idx,
            'snapshot_file': snapshot_file,
            'chain_hash': chain_hash,
            'ok': record_ok,
            'errors': errors,
        })
        if not record_ok:
            ok = False
        prev_chain = chain_hash
    return {'ok': ok, 'records': results}


def main():
    ap = argparse.ArgumentParser(description='Verify vulnerability snapshot chain')
    ap.add_argument('--signatures-file', default='audit/VULN_SNAPSHOTS_SIGNATURES.jsonl')
    ap.add_argument('--ed25519-pub', help='Path to raw 32-byte Ed25519 public key file')
    ap.add_argument('--json', action='store_true', help='Force JSON output (default)')
    args = ap.parse_args()
    try:
        with open(args.signatures_file, 'r', encoding='utf-8') as f:
            lines = [ln.strip() for ln in f if ln.strip()]
    except Exception as e:
        print(json.dumps({'ok': False, 'error': f'open_signatures_failed:{e}'}))
        sys.exit(1)
    ed_pub = None
    if args.ed25519_pub:
        if not _HAS_CRYPTO:
            print(json.dumps({'ok': False, 'error': 'cryptography_module_missing'}))
            sys.exit(1)
        try:
            ed_pub = load_ed25519_pub(args.ed25519_pub)
        except Exception as e:
            print(json.dumps({'ok': False, 'error': f'load_ed25519_pub_failed:{e}'}))
            sys.exit(1)
    hmac_key_env = os.getenv('NEURON_SNAPSHOT_HMAC_KEY')
    hmac_key = hmac_key_env.encode() if hmac_key_env else None
    summary = verify_chain(lines, ed_pub, hmac_key)
    print(json.dumps(summary, indent=2))
    sys.exit(0 if summary.get('ok') else 2)

if __name__ == '__main__':
    main()
