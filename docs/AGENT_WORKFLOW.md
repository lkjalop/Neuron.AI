# Agent Workflow

## Overview
The Agent Insights layer synthesizes detector outputs, calibration state, and fusion performance metrics to produce human-readable hypotheses.

```
Events -> Detectors (Baseline/SNN/Temporal) -> Calibration -> Fusion -> Policy Context -> Insights Engine -> Narratives
```

## Stages
1. Ingestion & Detection
2. Temporal Calibration & Quantile Tracking
3. Fusion & Weight Tuning
4. Policy Context Enrichment (quantile deltas, gating ratios)
5. Insights Engine Heuristics
6. Operator Action / Param Update (audited)

## Insight Heuristics (Initial)
- Temporal uplift deficit
- Calibration staleness
- Fusion suppression elevation
- Quantile distribution shift (p99 drift)

## Data Surfaces
- Metrics (Prometheus gauges/counters)
- Policy context snapshot (`policy_context().snapshot(tenant)`) returns temporal quantiles + gating ratio.
- Audit trail for parameter changes (`audit/param_changes.log`).

## Future Extensions
- Multi-head TFT probabilistic residuals
- Root cause narrative linking retrieval corpus context
- Automated remediation suggestions with confidence scoring

## Safety & Governance
- All parameter mutations routed through `update_param` with audit hash chaining.
- Insights are advisory: no automatic parameter changes beyond explicit tuner scope.
