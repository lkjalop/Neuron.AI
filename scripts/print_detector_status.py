"""Detector Status Script

Prints currently registered detectors, their cost ordering, and (if fusion
weights configured) the current weight values from the param store.

Usage:
  powershell> python scripts/print_detector_status.py

Environment Flags Impacting Output:
  ENABLE_FUSION=true      (shows fusion strategy + fused detector name)
  FUSION_STRATEGY=...     (defaults to weighted_temporal)

Exit code 0 always (informational script).
"""
from __future__ import annotations

import os
from detect.orchestrator import build_default_orchestrator
from runtime.param_store import get_param


def main():
    orch = build_default_orchestrator()
    print("== Detector Registry ==")
    for det in orch.registry.enabled():
        weight = None
        if os.getenv("ENABLE_FUSION", "false").lower() == "true":
            # Weight key pattern: fusion.weight.<detector>
            key = f"fusion.weight.{det.name}"
            try:
                weight = float(get_param(key, 1.0))
            except Exception:
                weight = None
        print(f"- {det.name} (cost_hint={getattr(det,'cost_hint', 'n/a')}" + (f", weight={weight}" if weight is not None else "") + ")")
    if os.getenv("ENABLE_FUSION", "false").lower() == "true":
        strat = os.getenv("FUSION_STRATEGY", "weighted_temporal")
        print(f"\nFusion Strategy: {strat}")
    else:
        print("\nFusion disabled (set ENABLE_FUSION=true to enable)")


if __name__ == "__main__":
    main()
