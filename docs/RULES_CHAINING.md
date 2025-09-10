# Rule DSL Chaining & Guards

This document describes the response rule DSL chaining semantics, guardrails, and related metrics.

## Chaining Basics
Each rule may optionally specify a `next` field referencing the `id` of another rule. When a rule evaluates (match or no_match) and a `next` is present, the engine proceeds to the referenced rule and continues evaluation until:
- The chain ends (rule has no `next`)
- A loop is detected (already visited rule id)
- Maximum depth is exceeded (safety bound)
- An evaluation error occurs

## Evaluation Safety Guards
To protect against runaway chains and cycles the engine enforces:
- Loop detection: set of visited rule ids; encountering the same id again stops execution and emits `loop_detected`.
- Depth cap: a fixed maximum (currently 25) number of chained transitions; exceeding it emits `depth_exceeded`.

## Metrics
| Metric | Type | Labels | Description |
| ------ | ---- | ------ | ----------- |
| `neuron_response_rule_chain_total` | Counter | `result` (`ok|loop_detected|depth_exceeded|error`) | Outcome of each chain evaluation root. |
| `neuron_response_rule_latency_seconds` | Histogram | `rule_id` | Per-rule evaluation latency. |
| `neuron_response_rule_reload_total` | Counter | `result` (`success|error|skipped`) | Rule file reload attempts. |

## Debugging Tips
1. Use `/response/rules/reload` after editing the rule file (configured via `RESPONSE_RULES_PATH`).
2. Scrape `/metrics` and search for `neuron_response_rule_chain_total` samples by result label to identify chaining issues.
3. Add temporary `print()` or logging inside rule actions if deeper tracing is needed (ensure logs do not contain secrets).

## Example
```yaml
- id: login_anomaly
  description: Detect anomalous login pattern
  match: "event.get('type') == 'login' and event.get('score',0) > 0.8"
  action: escalate
  next: geo_followup
- id: geo_followup
  description: Perform geo anomaly follow-up
  match: "event.get('geo_distance_km',0) > 1500"
  action: ticket
```

In this example, if `login_anomaly` matches it will immediately evaluate `geo_followup`. The resulting chain outcome increments `neuron_response_rule_chain_total{result="ok"}`.

## Failure Scenarios
| Scenario | Result Label | Notes |
| -------- | ------------ | ----- |
| Loop encountered | `loop_detected` | Rule A -> Rule B -> Rule A. |
| Depth exceeded | `depth_exceeded` | Chain longer than max depth. |
| Exception in rule eval | `error` | Exception during `match` expression or action logic. |

---
For broader system development details see `DEVELOPMENT.md`.
