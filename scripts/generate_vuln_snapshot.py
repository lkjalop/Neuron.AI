"""Generate vulnerability snapshot manifest with chained signature.

Outputs a JSONL file containing current vulnerabilities (DB preferred, fallback memory) plus
summary header, and appends a chained signature record (ed25519 preferred; HMAC fallback)
into audit/VULN_SNAPSHOTS_SIGNATURES.jsonl.

Usage:
  python scripts/generate_vuln_snapshot.py
Env:
  AUDIT_SIGNING_KEY (optional) - HMAC key
  AUDIT_ED25519_SEED (optional) - 32-byte hex seed for ed25519
"""
from __future__ import annotations
import os, sys, json, time, hashlib, pathlib, hmac
from typing import List, Dict, Any

try:
    from nacl import signing  # type: ignore
except Exception:  # noqa: BLE001
    signing = None  # type: ignore

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / 'artifacts' / 'vuln_snapshots'
OUT_DIR.mkdir(parents=True, exist_ok=True)
SNAP_SIGS = ROOT / 'audit' / 'VULN_SNAPSHOTS_SIGNATURES.jsonl'

async def _load_vulns() -> List[Dict[str, Any]]:
    try:
        from storage import vuln_store  # type: ignore
        from storage import postgres  # type: ignore
    except Exception:
        vuln_store = None  # type: ignore
    vulns: List[Dict[str, Any]] = []
    if vuln_store:
        try:
            rows = await postgres.fetch("SELECT * FROM vulnerabilities")  # type: ignore
            for r in rows:
                vulns.append(dict(r))
            return vulns
        except Exception:
            pass
    # Memory fallback
    try:
        from scanner.scanner_agent import _VULNS  # type: ignore
        for v in _VULNS.values():
            d = v.__dict__.copy()
            # serialize datetimes
            for k, val in list(d.items()):
                if hasattr(val, 'isoformat'):
                    try:
                        d[k] = val.isoformat()
                    except Exception:
                        pass
            vulns.append(d)
    except Exception:
        pass
    return vulns

def _prev_sig() -> str | None:
    if not SNAP_SIGS.exists():
        return None
    try:
        *_, last = SNAP_SIGS.read_text(encoding='utf-8').strip().splitlines()
        obj = json.loads(last)
        return obj.get('entry_hash') or obj.get('snapshot_hash')
    except Exception:
        return None

async def main():
    vulns = await _load_vulns()
    ts = time.time()
    record = {"generated_ts": ts, "count": len(vulns)}
    file_hash_acc = hashlib.sha256()
    out_path = OUT_DIR / f"snapshot_{int(ts)}.jsonl"
    with out_path.open('w', encoding='utf-8') as f:
        f.write(json.dumps({"_meta": record}) + "\n")
        for v in vulns:
            line = json.dumps(v, sort_keys=True)
            f.write(line + "\n")
            file_hash_acc.update(line.encode())
    snapshot_hash = file_hash_acc.hexdigest()
    prev = _prev_sig()
    chain_payload = json.dumps({"snapshot_hash": snapshot_hash, "prev": prev}, sort_keys=True).encode()
    entry_hash = hashlib.sha256(chain_payload).hexdigest()
    rec: Dict[str, Any] = {"ts": ts, "snapshot_hash": snapshot_hash, "prev": prev, "entry_hash": entry_hash}
    hmac_key = os.getenv('AUDIT_SIGNING_KEY')
    if hmac_key:
        rec['hmac_sig'] = hmac.new(hmac_key.encode(), chain_payload, hashlib.sha256).hexdigest()
    seed = os.getenv('AUDIT_ED25519_SEED')
    if seed and signing:
        try:
            seed_bytes = bytes.fromhex(seed)
            if len(seed_bytes) != 32:
                raise ValueError('seed must be 32 bytes')
            sk = signing.SigningKey(seed_bytes)
            sig = sk.sign(chain_payload).signature
            rec['ed25519_pubkey'] = sk.verify_key.encode().hex()
            rec['ed25519_sig'] = sig.hex()
            rec['alg'] = 'ed25519+chain'
        except Exception:
            rec['alg'] = 'hmac' if 'hmac_sig' in rec else 'none'
    else:
        rec['alg'] = 'hmac' if 'hmac_sig' in rec else 'none'
    with SNAP_SIGS.open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec) + '\n')
    print(json.dumps({"snapshot_file": str(out_path), **rec}, indent=2))

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
