#!/usr/bin/env python
"""Validation harness for local scanning MVP.

Steps:
 1. Enable scanning & reduce interval (120s -> 5s for test)
 2. Ingest sample SBOM (openssl + zlib)
 3. Poll findings endpoint until expected CVEs appear or timeout
 4. Validate ordering (openssl HIGH score > zlib MEDIUM) and exit 0 if success

Usage:
  python scripts/validate_scanner_local.py --api-key <ADMIN_KEY> [--base-url http://localhost:8000]
"""
from __future__ import annotations
import argparse, time, sys, json, urllib.request

DEFAULT_SBOM = {
    "asset_name": "validation-app",
    "document": {"components": [
        {"name": "openssl", "version": "3.0.13", "purl": "pkg:openssl/openssl@3.0.13"},
        {"name": "zlib", "version": "1.2.11", "purl": "pkg:zlib/zlib@1.2.11"}
    ]}
}

EXPECTED = ["CVE-2025-12345", "CVE-2024-22222"]


def _req(method: str, url: str, api_key: str, payload: dict | None = None):
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("x-api-key", api_key)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode()
            try:
                return json.loads(raw)
            except Exception:
                return raw
    except Exception as e:
        return {"error": str(e), "_url": url}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-key", required=True)
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--timeout", type=int, default=45)
    args = ap.parse_args()

    # Enable scanning & shorten interval
    for upd in [
        {"key": "vuln.scan.enabled", "value": True, "reason": "validation"},
        {"key": "vuln.scan.interval_seconds", "value": 5, "reason": "fast_cycle"},
    ]:
        _req("POST", f"{args.base_url}/admin/params/update", args.api_key, upd)

    # Ingest SBOM
    resp = _req("POST", f"{args.base_url}/vuln/ingest_sbom", args.api_key, DEFAULT_SBOM)
    if isinstance(resp, dict) and resp.get("count", 0) < 2:
        print("[WARN] SBOM ingestion returned unexpected component count", file=sys.stderr)

    # Poll findings
    start = time.time()
    found = []
    while time.time() - start < args.timeout:
        data = _req("GET", f"{args.base_url}/vuln/findings", args.api_key)
        try:
            items = data.get("items") if isinstance(data, dict) else []
        except Exception:
            items = []
        cves = {i.get("vulnerability_id") or i.get("cve_id") for i in items if isinstance(i, dict)}
        if all(e in cves for e in EXPECTED):
            found = [i for i in items if (i.get("vulnerability_id") in EXPECTED or i.get("cve_id") in EXPECTED)]
            break
        time.sleep(2)

    if not found:
        print("[FAIL] Expected CVEs not found within timeout", file=sys.stderr)
        sys.exit(1)

    # Check ordering by risk_score (openssl CVE should have higher or equal risk than zlib)
    scores = { (i.get("vulnerability_id") or i.get("cve_id")) : i.get("risk_score") for i in found }
    o_score = scores.get("CVE-2025-12345", -1)
    z_score = scores.get("CVE-2024-22222", -1)
    if o_score < z_score:
        print(f"[FAIL] Ordering unexpected: openssl {o_score} < zlib {z_score}", file=sys.stderr)
        sys.exit(2)

    print("[OK] Scanner validation passed: findings present & ordering valid")
    sys.exit(0)

if __name__ == "__main__":
    main()
