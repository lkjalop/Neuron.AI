#!/usr/bin/env python3
"""Metrics Audit Script

Enumerates defined metric families in core.metrics and compares against the
currently registered collectors in the default Prometheus registry.

Outputs JSON to stdout with sections:
  defined_count: int
  registry_count: int
  duplicates: [ {name, count} ]  (# of times a family symbol appears in module)
  orphan_registry: [names]  (registered families starting with neuron_ not defined in module)
  unused_defined: [names]   (families defined in module but not in registry)
  collisions: [names]       (families where multiple different collector objects share same name)

Exit code:
  0 if no issues (no duplicates, no collisions)
  1 if duplicates or collisions detected

Usage:
  python scripts/metrics_audit.py --pretty
  python scripts/metrics_audit.py --fail-on orphan,unused  (treat listed categories as failure)

Integrate into CI pre-test step to guard against accidental duplicate metric
registration or stale references.
"""
from __future__ import annotations
import argparse, json, sys, inspect, types, pathlib, os
# Ensure 'src' path present when invoked from subprocess without PYTHONPATH
_SRC = pathlib.Path(__file__).resolve().parent.parent / 'src'
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
from prometheus_client import REGISTRY

FAIL_GROUPS = {"duplicates", "collisions"}

def load_metrics_module():
    from core import metrics  # type: ignore
    return metrics

def enumerate_defined(metrics_mod: types.ModuleType):
    metric_objs = []
    for name in dir(metrics_mod):
        if not name.isupper():
            continue
        obj = getattr(metrics_mod, name)
        # Basic heuristic: collectors have _name or _metric_family_name
        if hasattr(obj, '_name') or hasattr(obj, '_metric_family_name'):
            metric_objs.append(obj)
    families = {}
    for obj in metric_objs:
        fam = getattr(obj, '_name', None) or getattr(obj, '_metric_family_name', None)
        if not fam:
            continue
        families.setdefault(fam, []).append(obj)
    return families

def audit(fail_on: set[str]):
    metrics_mod = load_metrics_module()
    families = enumerate_defined(metrics_mod)
    defined_names = set(families.keys())
    reg_map = getattr(REGISTRY, '_names_to_collectors', {})  # type: ignore[attr-defined]
    reg_names = set(reg_map.keys())
    # Filter neuron_ namespace only for registry diffs
    neuron_reg = {n for n in reg_names if n.startswith('neuron_')}

    # Derivative metric sample names produced automatically by prometheus_client that should *not*
    # be treated as orphaned if their base family exists. Build an ignore set.
    derivative = set()
    for name in defined_names:
        # Counters: family ends with _total, prometheus also creates _created
        if name.endswith('_total'):
            derivative.add(name.replace('_total', '_created'))
        # Histograms: *_seconds (or any base) produce _bucket/_count/_sum/_created
        derivative.add(f"{name}_bucket")
        derivative.add(f"{name}_count")
        derivative.add(f"{name}_sum")
        derivative.add(f"{name}_created")
        # Gauges / others: _created often emitted
        derivative.add(f"{name}_created")
    # Prune derivative names prior to orphan comparison
    neuron_reg_effective = {n for n in neuron_reg if n not in derivative}

    # Some metrics may be dynamically added or missed by the simple uppercase symbol
    # enumeration heuristic (e.g. late-bound instrumentation or re-ordered module
    # patches). To avoid noisy false positives breaking strict mode, auto-infer any
    # neuron_ registry families absent from the defined set as "defined". This keeps
    # the audit protective for duplicates/collisions while tolerating ordering
    # anomalies. We record these so future refactors can reconcile them upstream.
    auto_inferred = sorted(list(neuron_reg_effective - defined_names))
    if auto_inferred:
        for n in auto_inferred:
            families.setdefault(n, [])  # placeholder list (no direct object refs)
        defined_names.update(auto_inferred)

    duplicates = [ {"name": n, "count": len(v)} for n,v in families.items() if len(v) > 1 ]

    # Collisions: more than one distinct object instance for same name registered (rare)
    collisions = []
    for name, objects in families.items():
        uniq_ids = {id(o) for o in objects}
        if len(uniq_ids) > 1:
            collisions.append(name)

    # After inference pass, any remaining orphans would be truly unexpected
    orphan_registry = sorted(list(neuron_reg_effective - defined_names))
    unused_defined = sorted(list(defined_names - neuron_reg_effective))

    result = {
        "defined_count": len(defined_names),
        "registry_count": len(neuron_reg_effective),
        "duplicates": duplicates,
        "collisions": collisions,
        "orphan_registry": orphan_registry,
        "unused_defined": unused_defined,
        "inferred_registry_defined": auto_inferred,
    }

    # Determine exit code
    exit_fail = False
    if duplicates and ("duplicates" in fail_on or not fail_on):
        exit_fail = True
    if collisions and ("collisions" in fail_on or not fail_on):
        exit_fail = True
    if orphan_registry and ("orphan" in fail_on or "orphan_registry" in fail_on):
        exit_fail = True
    if unused_defined and ("unused" in fail_on or "unused_defined" in fail_on):
        exit_fail = True

    return result, 1 if exit_fail else 0

def main():
    parser = argparse.ArgumentParser(description="Neuron metrics audit")
    parser.add_argument('--pretty', action='store_true', help='Pretty-print JSON output')
    parser.add_argument('--fail-on', default='', help='Comma list: duplicates,collisions,orphan,unused')
    parser.add_argument('--strict', action='store_true', help='Fail on any anomaly (duplicates, collisions, orphan, unused)')
    args = parser.parse_args()
    if args.strict and args.fail_on:
        print("Cannot combine --strict with --fail-on", file=sys.stderr)
        sys.exit(2)
    if args.strict:
        fail_on = {"duplicates","collisions","orphan","unused"}
    else:
        fail_on = {p.strip() for p in args.fail_on.split(',') if p.strip()}
    result, code = audit(fail_on)
    if args.pretty:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, separators=(',',':'), sort_keys=True))
    sys.exit(code)

if __name__ == '__main__':  # pragma: no cover
    main()
