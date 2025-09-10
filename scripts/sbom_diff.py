"""Compare two CycloneDX SBOM JSON files and report component & vulnerability deltas.

Usage:
  python scripts/sbom_diff.py --prev artifacts/security/previous_sbom.json --current artifacts/security/sbom.json

Outputs:
  artifacts/security/sbom_diff.json
Fields:
  added_components, removed_components, updated_components (version change)
  added_vulns, removed_vulns (by id)
"""
from __future__ import annotations
import json, argparse, pathlib, sys
from typing import Dict, Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEC = ROOT / 'artifacts' / 'security'
SEC.mkdir(parents=True, exist_ok=True)

COMP_KEYS = ('components','bom','metadata')  # attempt flexible parse
VULN_KEYS = ('vulnerabilities','vulnerability')


def load(path: pathlib.Path) -> Dict[str, Any]:
    if not path.exists():
        print(f'[sbom-diff] missing {path}', file=sys.stderr)
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as e:  # noqa: BLE001
        print(f'[sbom-diff] failed parse {path}: {e}', file=sys.stderr)
        return {}


def extract_components(data: Dict[str, Any]):
    comps = []
    if 'components' in data and isinstance(data['components'], list):
        comps = data['components']
    return { (c.get('group'), c.get('name'), c.get('version')): c for c in comps if isinstance(c, dict) }


def extract_vulns(data: Dict[str, Any]):
    vulns = []
    if 'vulnerabilities' in data and isinstance(data['vulnerabilities'], list):
        vulns = data['vulnerabilities']
    out = {}
    for v in vulns:
        vid = v.get('id') or v.get('vulnerability', {}).get('id') or v.get('bom-ref')
        if vid:
            out[str(vid)] = v
    return out


def diff(prev: Dict[str, Any], current: Dict[str, Any]):
    pc = extract_components(prev)
    cc = extract_components(current)
    pv = extract_vulns(prev)
    cv = extract_vulns(current)

    added_c = [k for k in cc.keys() if k not in pc]
    removed_c = [k for k in pc.keys() if k not in cc]
    updated_c = []
    # detect same name/group with version change
    name_map_prev = {}
    name_map_curr = {}
    for (g,n,v) in pc.keys():
        name_map_prev.setdefault((g,n), []).append(v)
    for (g,n,v) in cc.keys():
        name_map_curr.setdefault((g,n), []).append(v)
    for key in name_map_prev.keys() & name_map_curr.keys():
        if set(name_map_prev[key]) != set(name_map_curr[key]):
            updated_c.append(key)

    added_v = [k for k in cv.keys() if k not in pv]
    removed_v = [k for k in pv.keys() if k not in cv]

    return {
        'added_components': added_c,
        'removed_components': removed_c,
        'updated_components': updated_c,
        'added_vulns': added_v,
        'removed_vulns': removed_v,
        'summary': {
            'components_prev': len(pc), 'components_current': len(cc),
            'vulns_prev': len(pv), 'vulns_current': len(cv),
        }
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prev', required=True)
    ap.add_argument('--current', required=True)
    ap.add_argument('--out', default=str(SEC / 'sbom_diff.json'))
    args = ap.parse_args()
    prev = load(pathlib.Path(args.prev))
    cur = load(pathlib.Path(args.current))
    report = diff(prev, cur)
    pathlib.Path(args.out).write_text(json.dumps(report, indent=2))
    print('[sbom-diff] components +', len(report['added_components']), '-', len(report['removed_components']), 'updated', len(report['updated_components']))
    print('[sbom-diff] vulns +', len(report['added_vulns']), '-', len(report['removed_vulns']))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
