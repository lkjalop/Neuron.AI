"""Insights & Policy Demo Script

Demonstrates end-to-end flow:
 1. Generate synthetic events
 2. Process through orchestrator to produce anomalies
 3. Feed anomalies to InsightsEngine
 4. Enrich resulting insight payloads with PolicyContextProvider

Usage:
  powershell> python scripts/demo_insights_policy.py --events 150 --tenant demo

Optional env flags (same as orchestrator):
  ENABLE_FUSION=true
  EXPERIMENTAL_ISOFOREST=true
  ENABLE_SNN=true
  SNN_DETERMINISTIC=true

Outputs:
  - Prints generated insights as JSON lines
  - Summary counts of anomalies vs insights
"""
from __future__ import annotations

import argparse, json, os
from detect.orchestrator import build_default_orchestrator
from ingest.adapters.synthetic import synthetic_stream
from insights.engine import InsightsEngine
from policy.context_provider import PolicyContextProvider


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", type=int, default=150, help="Number of synthetic events")
    ap.add_argument("--tenant", type=str, default="demo", help="Tenant ID")
    return ap.parse_args()


def main():
    args = parse_args()
    orch = build_default_orchestrator()
    insights_engine = InsightsEngine(burst_threshold=3)
    policy_ctx = PolicyContextProvider()

    # Seed some context
    policy_ctx.set_asset("srv-app-01", 5)
    policy_ctx.set_asset("srv-db-01", 9)
    policy_ctx.set_user("alice", 2)
    policy_ctx.set_user("malory", 8)

    anomaly_total = 0
    for evt in synthetic_stream(count=args.events, anomaly_period=37, tenant_id=args.tenant):
        # Add a few asset/user fields to synthetic event if missing
        if not getattr(evt, 'asset', None):
            evt.payload['asset'] = 'srv-app-01'
        evt.payload.setdefault('user', 'alice')
        anomalies = orch.process_event(evt)
        anomaly_total += len(anomalies)
        insights_engine.ingest(anomalies)

    insights = insights_engine.generate()
    print(f"Generated {len(insights)} insights from {anomaly_total} anomalies\n")
    for ins in insights:
        enriched = policy_ctx.enrich(ins.to_dict())
        print(json.dumps(enriched))

    print("\nDemo complete")


if __name__ == "__main__":
    main()
