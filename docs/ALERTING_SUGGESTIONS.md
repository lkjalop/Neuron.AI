# Alerting Suggestions (Batch 4 Observability)

These Prometheus alert rule examples cover newly added and existing metrics. Tune thresholds based on baseline SLOs and environment scale. Durations (`for:`) mitigate alert flapping.

## 1. Fusion Suppression Rate Overrun
High sustained suppression may indicate overly aggressive thresholding or upstream noise.
```
- alert: FusionSuppressionOverrun
  expr: avg_over_time(neuron_fusion_suppression_rate[5m]) > 0.90
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: High fusion suppression rate
    description: Suppression rate >90% for 10m (possible recall degradation)
```

## 2. Circuit Breaker Open (Latency / Error Guard)
Detect breaker open state persisting.
```
- alert: RetrievalCircuitBreakerOpen
  expr: neuron_rag_circuit_open_state > 0
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: Retrieval circuit breaker open
    description: Retrieval circuit breaker has been open >2m; investigate upstream latency/errors.
```

## 3. Circuit Breaker Thrashing
Frequent transitions (optional if trip history exported as counter `neuron_rag_circuit_breaker_trips_total`).
```
- alert: RetrievalCircuitBreakerThrash
  expr: increase(neuron_rag_circuit_breaker_trips_total[15m]) > 5
  labels:
    severity: warning
  annotations:
    summary: Retrieval circuit breaker thrashing
    description: More than 5 breaker trips in 15m window.
```

## 4. Temporal Buffer Readiness Degradation
Retained ratio indicates aggressive compaction or data loss.
```
- alert: TemporalBufferRetentionDrop
  expr: avg_over_time(neuron_temporal_buffer_retained_ratio[10m]) < 0.60
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: Temporal buffer retained ratio low
    description: Average retained ratio <60% over last 10m (consider increasing compaction factors or window size).
```

## 5. Temporal Buffer Not Ready (Per Tenant)
```
- alert: TemporalBufferNotReady
  expr: neuron_temporal_buffer_ready == 0
  for: 15m
  labels:
    severity: info
  annotations:
    summary: Temporal buffer not reaching readiness threshold
    description: Buffer has remained below readiness threshold for 15m.
```

## 6. Strategy Fallback Surge
```
- alert: FusionStrategyFallbackSpike
  expr: increase(neuron_fusion_strategy_fallback_total[10m]) > 0
  labels:
    severity: info
  annotations:
    summary: Fusion strategy fallback executed
    description: Strategy fallback occurred in last 10m; review precision proxy metrics.
```

## 7. Memory Signal Gating Latency Regression
```
- alert: MemorySignalGatingLatencyHigh
  expr: histogram_quantile(0.95, sum by (le) (rate(neuron_memory_signal_gating_latency_seconds_bucket[5m]))) > 0.25
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: Elevated memory signal gating latency
    description: 95th percentile >250ms over 5m window.
```

## 8. Retrieval Latency Degradation
```
- alert: RetrievalLatencyP95High
  expr: histogram_quantile(0.95, sum by (le) (rate(neuron_rag_retrieval_latency_seconds_bucket[5m]))) > 2
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: Retrieval latency regression
    description: P95 retrieval latency >2s for 10m (check embedding service or vector store).
```

## 9. Embedding Cache Ineffective
```
- alert: EmbeddingCacheMissSpike
  expr: rate(neuron_rag_embedding_cache_misses_total[5m]) / ( rate(neuron_rag_embedding_cache_misses_total[5m]) + rate(neuron_rag_embedding_cache_hits_total[5m]) ) > 0.40
  for: 15m
  labels:
    severity: info
  annotations:
    summary: Embedding cache hit ratio degraded
    description: Cache miss ratio >40% for 15m.
```

## 10. Rule Evaluation Error Ratio (If error counter exists)
Assuming counter `neuron_response_rule_chain_total{result="error"}` and total attempts = sum of all results.
```
- alert: RuleEvaluationErrorRate
  expr: (increase(neuron_response_rule_chain_total{result="error"}[10m])) / (increase(neuron_response_rule_chain_total[10m])) > 0.05
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: Rule evaluation error rate high
    description: >5% of rule chain evaluations failing.
```

## 11. Drift Guard Triggers
```
- alert: DriftGuardActive
  expr: increase(neuron_snn_drift_guard_trips_total[15m]) > 0
  labels:
    severity: info
  annotations:
    summary: Drift guard triggered
    description: Drift guard action in last 15m. Review /governance/drift/trace for details.
```

## 12. Suppression Threshold Churn (Autotune)
```
- alert: SuppressionAutotuneChurn
  expr: increase(neuron_fusion_suppress_autotune_adjustments_total[1h]) > 6
  labels:
    severity: info
  annotations:
    summary: High suppression autotune adjustment rate
    description: >6 adjustments in the last hour (verify stability of precision proxy metrics).
```

## 13. Memory Pattern Store Evictions
```
- alert: MemoryPatternEvictionBurst
  expr: increase(neuron_memory_pattern_evictions_total{reason="capacity"}[10m]) > 50
  labels:
    severity: warning
  annotations:
    summary: Memory pattern capacity evictions high
    description: >50 capacity evictions in 10m; consider increasing limits.
```

## 14. Circuit Breaker Open Duration (If duration gauge present)
```
- alert: RetrievalBreakerOpenDuration
  expr: neuron_rag_circuit_open_duration_seconds > 120
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: Retrieval circuit breaker open >120s
    description: Prolonged open state indicates systemic backend issues.
```

---
### Dashboard Tips
- Show `neuron_temporal_buffer_retained_ratio` alongside `neuron_temporal_buffer_size` to visualize compaction impact.
- Overlay `neuron_fusion_strategy_fallback_total` rate with precision proxy false positive rates to correlate cause.
- Add retrieval latency quantiles and breaker state on a single panel to track cascading failures.

### Tuning Guidance
- Start conservative (higher thresholds) and gradually tighten after observing normal steady-state.
- Revisit dynamic thresholds (e.g., suppression overrun) once precision proxy stabilization metrics are mature.

### Future Candidates
- Governance composite score deviation (when formalized).
- Ticket SLA breach rate once SLA metrics are exported.

Use these as a baseline; integrate into `prometheus_alert_rules.yml` or a dedicated alert rules file as your observability matures.
