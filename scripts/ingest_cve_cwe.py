"""Lightweight CVE/CWE Ingestion Script (Seed Ontology)

Purpose:
  Bootstrap a minimal local knowledge store mapping CVE -> CWE and simple keyword signals
  to support early anomaly tagging & future RAG / ontology expansion.

Data Sources (expected JSON lines or simple CSV style for MVP):
  - input file containing lines of: {"cve": "CVE-2024-1234", "cwe": "CWE-79", "keywords": ["xss","script","reflected"]}

Usage:
  powershell> python scripts/ingest_cve_cwe.py --input data/cve_seed.jsonl --out artifacts/ontology/cve_cwe_store.json

Output:
  JSON object: {
     "version": "0.1.0",
     "count": <int>,
     "entries": { "CVE-2024-1234": {"cwe": "CWE-79", "keywords": ["xss","script"], "ts": 1693820000 } },
     "hash": "<hex16>"
  }

Determinism:
  Sorted keys, stable JSON dump; hash = first 16 hex of SHA256 over canonical (excluding hash field).
"""
from __future__ import annotations

import argparse, json, pathlib, time, hashlib

def load_entries(path: pathlib.Path):
    entries = {}
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                cve = obj.get('cve')
                if not cve:
                    continue
                entries[cve] = {
                    'cwe': obj.get('cwe'),
                    'keywords': obj.get('keywords') or [],
                    'ts': int(time.time())
                }
            except Exception:
                continue
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--out', default='artifacts/ontology/cve_cwe_store.json')
    args = ap.parse_args()
    inp = pathlib.Path(args.input)
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    entries = load_entries(inp)
    doc = {
        'version': '0.1.0',
        'count': len(entries),
        'entries': dict(sorted(entries.items(), key=lambda kv: kv[0]))
    }
    canonical = json.dumps(doc, separators=(',', ':'), sort_keys=True)
    doc['hash'] = hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]
    with out.open('w', encoding='utf-8') as f:
        json.dump(doc, f, indent=2, sort_keys=True)
    print(f"[cve_cwe_ingest] wrote {out} entries={doc['count']} hash={doc['hash']}")

if __name__ == '__main__':  # pragma: no cover
    main()
