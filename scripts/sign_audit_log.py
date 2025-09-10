"""Audit log signing scaffold.

Generates an HMAC-SHA256 signature over the full audit/AUDIT_LOG.md content
using a secret provided via AUDIT_SIGNING_KEY environment variable. The output
JSON (timestamp, hash, signature) is appended to audit/AUDIT_LOG_SIGNATURES.jsonl.

Future upgrade: migrate to ed25519 detached signatures; keep HMAC for early
phase simplicity.
"""
from __future__ import annotations
import os, sys, hmac, hashlib, json, time, pathlib
try:
    from nacl import signing  # type: ignore
except Exception:  # noqa: BLE001
    signing = None  # type: ignore

ROOT = pathlib.Path(__file__).resolve().parent.parent
AUDIT_LOG = ROOT / "audit" / "AUDIT_LOG.md"
SIG_FILE = ROOT / "audit" / "AUDIT_LOG_SIGNATURES.jsonl"

def _read_last_sig() -> str | None:
    if not SIG_FILE.exists():
        return None
    try:
        *_, last_line = SIG_FILE.read_text(encoding="utf-8").strip().splitlines()
        obj = json.loads(last_line)
        return obj.get("entry_hash") or obj.get("hash")
    except Exception:
        return None


def main():
    hmac_key = os.getenv("AUDIT_SIGNING_KEY")
    ed25519_seed = os.getenv("AUDIT_ED25519_SEED")  # 32-byte hex
    if not hmac_key and not (ed25519_seed and signing):
        print("No signing material (HMAC or ed25519) configured", file=sys.stderr)
        sys.exit(1)
    data = AUDIT_LOG.read_bytes()
    content_hash = hashlib.sha256(data).hexdigest()
    prev_hash = _read_last_sig()
    chain_payload = json.dumps({"hash": content_hash, "prev": prev_hash}, sort_keys=True).encode()
    entry_hash = hashlib.sha256(chain_payload).hexdigest()

    record: dict[str, str | float | None] = {
        "ts": time.time(),
        "hash": content_hash,
        "prev": prev_hash,
        "entry_hash": entry_hash,
    }

    # HMAC signature (always if key present)
    if hmac_key:
        record["hmac_alg"] = "HMAC-SHA256"
        record["hmac_sig"] = hmac.new(hmac_key.encode(), chain_payload, hashlib.sha256).hexdigest()

    # ed25519 signature (preferred if available)
    if ed25519_seed and signing:
        try:
            seed_bytes = bytes.fromhex(ed25519_seed)
            if len(seed_bytes) != 32:
                raise ValueError("seed must be 32 bytes hex")
            sk = signing.SigningKey(seed_bytes)
            sig = sk.sign(chain_payload).signature
            record["ed25519_pubkey"] = sk.verify_key.encode().hex()
            record["ed25519_sig"] = sig.hex()
            record["alg"] = "ed25519+chain"
        except Exception:
            record["alg"] = record.get("hmac_alg", "hmac_only")
    else:
        record["alg"] = record.get("hmac_alg", "hmac_only")

    with SIG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print(json.dumps(record, indent=2))

if __name__ == "__main__":
    main()
