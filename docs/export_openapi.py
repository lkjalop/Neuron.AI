"""Export the FastAPI OpenAPI schema to JSON (and optional lightweight markdown summary).

Usage:
    python docs/export_openapi.py --out artifacts/openapi.json [--markdown docs/API_REFERENCE.md]

This script imports the FastAPI `app` from `core.main` and serializes its OpenAPI schema.
It avoids side effects (no server start). Ensure PYTHONPATH includes project root.
"""
from __future__ import annotations
import argparse, json, pathlib, sys

# Attempt to ensure src directory is importable when run from repo root
ROOT = pathlib.Path(__file__).resolve().parents[1]
src = ROOT / 'src'
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from core.main import app  # type: ignore  # noqa: E402

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, help='Output JSON path for OpenAPI schema')
    ap.add_argument('--markdown', help='Optional markdown file to append summary stats to')
    args = ap.parse_args()
    schema = app.openapi()
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(schema, indent=2), encoding='utf-8')
    print(f"[export_openapi] Wrote schema to {out_path}")
    if args.markdown:
        md_path = pathlib.Path(args.markdown)
        if md_path.exists():
            try:
                endpoints = len(schema.get('paths', {}))
                comp_schemas = len(schema.get('components', {}).get('schemas', {}))
                with md_path.open('a', encoding='utf-8') as f:
                    f.write(f"\n\n<!-- OpenAPI Export Summary -->\n")
                    f.write(f"Exported endpoints: {endpoints}; component schemas: {comp_schemas}.\n")
                print(f"[export_openapi] Appended summary to {md_path}")
            except Exception as e:  # pragma: no cover
                print(f"[export_openapi] Failed to append markdown summary: {e}")

if __name__ == '__main__':
    main()
