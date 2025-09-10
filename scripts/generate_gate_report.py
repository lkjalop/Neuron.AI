"""Generate Phase Gate evidence bundle.

Aggregates:
- Runtime parameter snapshot
- Evaluation metrics artifact (baseline_metrics.json)
- Threshold sweep summary (threshold_sweep.json)
- Load harness results (perf/load_metrics.json)
- Latest anomaly dataset manifest (artifacts/dataset/manifest_*.json)
- Canonical phases doc hash
- Audit log tail + recent parameter change tail
- System resource snapshot

Computes SHA256 for each included artifact for integrity referencing in audit entry.
Outputs JSON + Markdown summary under artifacts/gate_report.
"""
from __future__ import annotations

import json
import hashlib
import time
import glob
import re
import argparse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None  # type: ignore

from config import runtime_params

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "artifacts"
REPORT_DIR = ART / "gate_report"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def canonical_doc_hash() -> Optional[str]:
    doc = ROOT / "docs" / "NEURON_PHASES.md"
    if not doc.exists():
        return None
    data = doc.read_bytes()
    return hashlib.sha256(data).hexdigest()


def latest_dataset_manifest() -> Optional[Path]:
    base = ART / "dataset"
    if not base.exists():
        return None
    cands = sorted(base.glob("manifest_*.json"))
    if not cands:
        return None
    return cands[-1]


def tail_audit(n: int = 25) -> str:
    path = ROOT / "audit" / "AUDIT_LOG.md"
    if not path.exists():
        return ""
    lines = path.read_text().splitlines()
    return "\n".join(lines[-n:])


def system_snapshot() -> Dict[str, Any]:
    if not psutil:
        return {"psutil": False}
    proc = psutil.Process()
    with proc.oneshot():  # type: ignore
        mem = proc.memory_info().rss / (1024 * 1024)
        cpu = proc.cpu_percent(interval=0.05)
    return {"memory_mb": mem, "cpu_percent": cpu}


def load_json(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if path and path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return None
    return None


def sha256_file(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def param_change_tail(n: int = 20) -> str:
    path = ROOT / 'audit' / 'param_changes.log'
    if not path.exists():
        return ''
    lines = path.read_text().splitlines()
    return '\n'.join(lines[-n:])


METRIC_PATTERNS = {
    'overlap_ratio': re.compile(r'^neuron_fusion_overlap_ratio\{tenant="(?P<tenant>[^"]+)"\} (?P<value>[-0-9.]+)$'),
    'snn_unique_ratio': re.compile(r'^neuron_fusion_snn_unique_ratio\{tenant="(?P<tenant>[^"]+)"\} (?P<value>[-0-9.]+)$'),
    'suppression_rate': re.compile(r'^neuron_fusion_suppression_rate\{tenant="(?P<tenant>[^"]+)"\} (?P<value>[-0-9.]+)$'),
    'suppression_alerts': re.compile(r'^neuron_fusion_suppression_alerts_total\{tenant="(?P<tenant>[^"]+)",strategy="(?P<strategy>[^"]+)"\} (?P<value>[-0-9.]+)$'),
}


def scrape_metrics(url: str) -> dict:
    out: Dict[str, Any] = {k: {} for k in METRIC_PATTERNS}
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:  # nosec B310 internal usage
            for raw_line in resp.read().decode('utf-8', errors='ignore').splitlines():
                line = raw_line.strip()
                if not line or line.startswith('#'):
                    continue
                for key, pat in METRIC_PATTERNS.items():
                    m = pat.match(line)
                    if m:
                        gd = m.groupdict()
                        tenant = gd.get('tenant') or 'unknown'
                        value = float(gd.get('value', '0') or 0)
                        if key == 'suppression_alerts':
                            strat = gd.get('strategy', '?')
                            out[key].setdefault(tenant, {})[strat] = value
                        else:
                            out[key][tenant] = value
                        break
    except Exception:
        pass
    return out


def fusion_table(metrics_data: dict) -> str:
    tenants = sorted(set(list(metrics_data['overlap_ratio'].keys()) + list(metrics_data['suppression_rate'].keys())))
    if not tenants:
        return 'No fusion metrics captured.'
    lines = [
        '| Tenant | Overlap Ratio | SNN Unique Ratio | Suppression Rate | Alerts (strategy->count) |',
        '|--------|---------------|------------------|------------------|----------------------------|'
    ]
    def fmt(v):
        return '-' if v is None else f"{v:.3f}"
    for t in tenants:
        overlap_v = metrics_data['overlap_ratio'].get(t)
        snn_unique_v = metrics_data['snn_unique_ratio'].get(t)
        supp_rate = metrics_data['suppression_rate'].get(t)
        alerts_map = metrics_data['suppression_alerts'].get(t, {})
        alerts_fmt = ', '.join(f"{k}:{int(v)}" for k, v in sorted(alerts_map.items())) or '-'
        lines.append(f"| {t} | {fmt(overlap_v)} | {fmt(snn_unique_v)} | {fmt(supp_rate)} | {alerts_fmt} |")
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Generate phase gate report with optional live fusion metrics snapshot')
    parser.add_argument('--metrics-url', help='Prometheus metrics endpoint (e.g. http://localhost:8000/metrics)')
    args = parser.parse_args()
    timestamp = int(time.time())
    param_snapshot = runtime_params.list_params()
    eval_path = ART / 'eval' / 'baseline_metrics.json'
    sweep_path = ART / 'eval' / 'threshold_sweep.json'
    load_path = ART / 'perf' / 'load_metrics.json'
    dataset_manifest = latest_dataset_manifest()

    artifacts: Dict[str, Dict[str, Any]] = {}
    for label, path in [
        ("evaluation_metrics", eval_path),
        ("threshold_sweep", sweep_path),
        ("load_metrics", load_path),
        ("dataset_manifest", dataset_manifest),
    ]:
        if path and path.exists():
            artifacts[label] = {
                "path": str(path),
                "sha256": sha256_file(path),
            }

    fusion_metrics = None
    if args.metrics_url:
        fusion_metrics = scrape_metrics(args.metrics_url)

    report: Dict[str, Any] = {
        "generated_at": timestamp,
        "parameters": param_snapshot,
        "evaluation_metrics": load_json(eval_path),
        "threshold_sweep": load_json(sweep_path),
        "load_metrics": load_json(load_path),
        "dataset_manifest": load_json(dataset_manifest),
        "artifacts": artifacts,
        "canonical_doc_hash": canonical_doc_hash(),
        "audit_log_tail": tail_audit(),
        "param_change_tail": param_change_tail(),
        "system_snapshot": system_snapshot(),
        "fusion_metrics_raw": fusion_metrics,
        "metrics_url": args.metrics_url,
    }

    json_path = REPORT_DIR / f"gate_report_{timestamp}.json"
    json_path.write_text(json.dumps(report, indent=2))

    # Simple markdown summary
    md_lines = [
        f"# Phase Gate Report ({timestamp})",
        "",
        f"Canonical Doc Hash: `{report['canonical_doc_hash']}`",
        "",
        "## Parameters",
        "```json",
        json.dumps(report["parameters"], indent=2),
        "```",
        "## Fusion & Suppression Metrics Snapshot",
        f"Source: {args.metrics_url or 'N/A'}",
    ]
    if fusion_metrics:
        md_lines.append(fusion_table(fusion_metrics))
    else:
        md_lines.append('No metrics snapshot collected.')
    md_lines.extend([
        "## Evaluation Metrics",
        "```json",
        json.dumps(report["evaluation_metrics"], indent=2),
        "```",
        "## Threshold Sweep",
        "```json",
        json.dumps(report["threshold_sweep"], indent=2),
        "```",
        "## Load Metrics",
        "```json",
        json.dumps(report["load_metrics"], indent=2),
        "```",
        "## Dataset Manifest (excerpt)",
        "```json",
        json.dumps(report["dataset_manifest"], indent=2),
        "```",
        "## Artifacts",
        "```json",
        json.dumps(report["artifacts"], indent=2),
        "```",
        "## System Snapshot",
        "```json",
        json.dumps(report["system_snapshot"], indent=2),
        "```",
        "## Audit Log Tail",
        "```",
        report["audit_log_tail"],
        "```",
        "## Parameter Change Tail",
        "```",
        report["param_change_tail"],
        "```",
    ])
    md_path = REPORT_DIR / f"gate_report_{timestamp}.md"
    md_path.write_text("\n".join(md_lines))
    print(f"Gate report generated: {json_path}")


if __name__ == "__main__":  # pragma: no cover
    main()
