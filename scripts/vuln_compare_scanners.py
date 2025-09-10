"""Compare Trivy and Grype vulnerability scan results.

Input (default paths):
  artifacts/security/trivy.json
  artifacts/security/grype.json

Outputs:
  artifacts/security/scanner_overlap.json
  stdout summary table

Metrics Computed:
- total_trivy / total_grype
- shared (by (id, severity))
- unique_trivy / unique_grype counts
- severity distribution overlap
- jaccard index (shared / union)

Usage:
  python scripts/vuln_compare_scanners.py \
      --trivy artifacts/security/trivy.json \
      --grype artifacts/security/grype.json
"""
from __future__ import annotations
import json, argparse, pathlib, sys, collections

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEC = ROOT / 'artifacts' / 'security'
SEC.mkdir(parents=True, exist_ok=True)

NORMALIZE_KEYS = ('VulnerabilityID','vulnerabilityID','id')
SEV_KEYS = ('Severity','severity')


def _extract_items(data):
    # Support Trivy & Grype JSON shapes loosely
    if isinstance(data, dict):
        if 'Results' in data:  # Trivy format
            for r in data.get('Results', []) or []:
                for vuln in r.get('Vulnerabilities', []) or []:
                    yield vuln
        elif 'matches' in data:  # Grype format
            for m in data.get('matches', []) or []:
                vuln = m.get('vulnerability') or {}
                yield vuln
        elif 'vulnerabilities' in data:  # fallback simple list
            for v in data.get('vulnerabilities') or []:
                yield v


def _get_id(obj):
    for k in NORMALIZE_KEYS:
        v = obj.get(k)
        if v:
            return str(v)
    return None


def _get_sev(obj):
    for k in SEV_KEYS:
        v = obj.get(k)
        if v:
            return str(v).upper()
    return 'UNKNOWN'


def load(path: pathlib.Path):
    if not path.exists():
        print(f'[overlap] missing file {path}', file=sys.stderr)
        return []
    try:
        return list(_extract_items(json.loads(path.read_text())))
    except Exception as e:  # noqa: BLE001
        print(f'[overlap] failed parse {path}: {e}', file=sys.stderr)
        return []


def analyze(trivy_items, grype_items):
    t_map = {(_get_id(o), _get_sev(o)) for o in trivy_items if _get_id(o)}
    g_map = {(_get_id(o), _get_sev(o)) for o in grype_items if _get_id(o)}
    shared = t_map & g_map
    unique_t = t_map - g_map
    unique_g = g_map - t_map
    union = t_map | g_map
    sev_dist = collections.Counter([sev for _, sev in shared])
    return {
        'total_trivy': len(t_map),
        'total_grype': len(g_map),
        'shared': len(shared),
        'unique_trivy': len(unique_t),
        'unique_grype': len(unique_g),
        'jaccard': (len(shared) / len(union)) if union else 0.0,
        'severity_shared_distribution': dict(sev_dist),
        'sample_unique_trivy': list(unique_t)[:20],
        'sample_unique_grype': list(unique_g)[:20],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--trivy', default=str(SEC / 'trivy.json'))
    ap.add_argument('--grype', default=str(SEC / 'grype.json'))
    ap.add_argument('--out', default=str(SEC / 'scanner_overlap.json'))
    args = ap.parse_args()
    t_items = load(pathlib.Path(args.trivy))
    g_items = load(pathlib.Path(args.grype))
    report = analyze(t_items, g_items)
    pathlib.Path(args.out).write_text(json.dumps(report, indent=2))
    print('[overlap] Trivy:', report['total_trivy'], 'Grype:', report['total_grype'])
    print('[overlap] Shared:', report['shared'], 'Jaccard:', f"{report['jaccard']:.3f}")
    print('[overlap] Unique Trivy:', report['unique_trivy'], 'Unique Grype:', report['unique_grype'])
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
