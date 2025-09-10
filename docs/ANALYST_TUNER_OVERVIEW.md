# Fusion Weight Tuner (Analyst Overview)

## Purpose
The fusion weight tuner automatically adjusts how much influence each detector has in the fused anomaly score. It pursues two analyst-aligned goals:
1. Reward detectors that contribute *unique* high-signal anomalies (they add coverage).
2. Penalize detectors that frequently fire during low-signal "noise" periods (proxy for false positives).

This keeps the fused signal focused and reduces alert fatigue without manual retuning.

## Key Concepts
| Term | Meaning |
|------|---------|
| Unique Contribution Ratio | Portion of union anomaly events where a detector was the *only* one firing. Signals complementary coverage. |
| Precision Proxy False-Positive Rate | Rate at which a detector fires inside designated low-signal windows (heuristic noise regions). High rate implies likely false positives. |
| Fusion Weight | Scaling factor applied to a detector's anomaly score when constructing a fused anomaly. |

## Adjustment Logic (Simplified)
1. If detector false-positive rate exceeds penalty threshold, weight is *reduced* (stronger reduction after a hard cap).
2. Else, if unique ratio above high threshold, weight nudged up.
3. Else, if unique ratio below low threshold, weight nudged down.
4. Cooldown prevents rapid oscillations (minimum interval between changes).

All changes are small, incremental, and bounded between a minimum and maximum safe range.

## Why This Helps Analysts
| Analyst Pain | Tuner Benefit |
|--------------|---------------|
| Too many similar low-value alerts | Penalizes detectors that add redundant noise. |
| Hard to justify detector inclusion | Provides auditable history of weight changes with reason codes. |
| Drift in environment causes detector imbalance | Continuous micro-adjustments adapt without full retraining. |
| Need transparency for audits | Every change logged to a JSON Lines history file. |

## History & Transparency
Adjustments are appended to: `artifacts/tuner/weight_history.jsonl` with fields:
```
{
  "ts": <timestamp>,
  "detector": "baseline",
  "old_weight": 1.0,
  "new_weight": 0.95,
  "delta": -0.05,
  "unique_ratio": 0.032,
  "fp_rate": 0.288,
  "reason": "fp_rate_penalty=0.288"
}
```
This can be ingested into dashboards or a knowledge base to explain why fusion outcomes changed over time.

## Typical Thresholds
| Parameter | Default | Interpretation |
|-----------|---------|---------------|
| `TUNER_HIGH_THRESHOLD` | 0.30 | Detector is strongly complementary above this. |
| `TUNER_LOW_THRESHOLD` | 0.05 | Detector adds little unique value below this. |
| `TUNER_FP_RATE_PENALTY_THRESHOLD` | 0.25 | Start penalizing above this FP rate. |
| `TUNER_FP_RATE_HARD_CAP` | 0.40 | Apply stronger penalty above this rate. |

## Operational Recommendations
1. Let the tuner run for at least one full daily cycle before judging impact.
2. Export the history file into your reporting system weekly to show precision improvements.
3. If a detector keeps getting penalized, investigate its rule set or calibration window.
4. For experimental detectors, start with a modest weight (e.g., 0.7) and allow tuner to promote if warranted.

## Disabling or Freezing
Set a fixed weight in the parameter store and stop the tuner process to freeze weighting during incident reviews.

## Roadmap Enhancements (Future)
- Integrate knowledge graph context (e.g., elevate detector weights if mapping to high-value MITRE techniques).
- Multi-objective scoring (precision + time-to-detect improvements).
- Adaptive learning rate based on variance of recent changes.

---
*This document is written for non-technical SOC and risk stakeholders to understand why automated weight adjustments improve alert quality.*
