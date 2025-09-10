from __future__ import annotations
import argparse
import json
import sys
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Any

from .plugins.base import ScanContext, ScannerPlugin
from .plugins.dummy_example import DummyExposurePlugin
from .model.finding import Finding
from .scoring.exploitability import blend_score
from .neuromorphic.signal import compute_neuromorphic_signal

try:
    import importlib
except ImportError:  # very unlikely
    import importlib

PLUGIN_REGISTRY = {
    DummyExposurePlugin.key: DummyExposurePlugin,
}


def load_params() -> Dict[str, Any]:
    # Minimal parameter loader: read defaults file if exists
    defaults_path = Path("config/runtime_params.defaults.json")
    if defaults_path.exists():
        try:
            return json.loads(defaults_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def iter_events(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def build_manifest(findings: List[Finding], params: Dict[str, Any], neu_signal: float, plugins: List[str]) -> Dict[str, Any]:
    raw = {
        "ts": time.time(),
        "count": len(findings),
        "plugins": plugins,
        "neu_signal": neu_signal,
        "param_keys": sorted([k for k in params.keys() if k.startswith("scanner.")]),
    }
    raw_json = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    raw_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()[:16]
    raw["manifest_hash"] = raw_hash
    return raw


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="Minimal Phase 1 scanner")
    ap.add_argument("--input", required=True, help="Path to JSONL events file")
    ap.add_argument("--out", required=True, help="Output findings JSONL path")
    ap.add_argument("--manifest", required=True, help="Output manifest JSON path")
    ap.add_argument("--plugins", default="dummy_exposure", help="Comma list of plugins")
    args = ap.parse_args(argv)

    params = load_params()

    plugin_keys = [p.strip() for p in args.plugins.split(",") if p.strip()]
    plugins: List[ScannerPlugin] = []
    for key in plugin_keys:
        cls = PLUGIN_REGISTRY.get(key)
        if not cls:
            print(f"WARN: plugin {key} not found", file=sys.stderr)
            continue
        plugins.append(cls())

    events_cache = list(iter_events(Path(args.input)))
    neu_signal = compute_neuromorphic_signal(events_cache, params)
    params["_neu_signal"] = neu_signal

    findings: List[Finding] = []
    ctx = ScanContext(params=params, ontology_store={})  # TODO: integrate ontology store

    for plugin in plugins:
        raw_findings = plugin.scan(events_cache, ctx)
        # Recompute blended score using scoring module for consistency
        for f in raw_findings:
            f.score = blend_score(f.exploitability, f.severity, params)
            f.compute_fingerprint()
        findings.extend(raw_findings)

    # Write findings JSONL
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fo:
        for f in findings:
            fo.write(json.dumps(f.to_dict(), sort_keys=True) + "\n")

    manifest = build_manifest(findings, params, neu_signal, plugin_keys)
    with Path(args.manifest).open("w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2, sort_keys=True)

    print(f"Wrote {len(findings)} findings; neu_signal={neu_signal}")
    return 0

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
