# Metrics Reference (Scaffold)

This document enumerates key `neuron_` Prometheus metric families currently exposed. It is a living scaffold; expand descriptions and add SLO owners as the platform matures.

## Cardinality Practices
- Tenant labeled metrics guarded by runtime limit `METRIC_TENANT_LABEL_LIMIT` (default 200). Exceeding new tenants are dropped and counted in `neuron_cardinality_guard_drops_total{metric,label}`.
- Prefer low-cardinality labels: (tenant, detector, outcome, reason, status, phase, step, rule_id).

## Core Retrieval & RAG
| Metric | Type | Labels | Notes |
|--------|------|--------|-------|
| neuron_rag_embedding_cache_hits_total | Counter | (none) | Cache hits for deterministic embedding cache |
| neuron_rag_embedding_cache_misses_total | Counter | (none) | Cache misses |
| neuron_rag_embedding_cache_evictions_total | Counter | reason | Evictions by reason (capacity|ttl) |
| neuron_rag_embedding_cache_size | Gauge | (none) | Current cache entries |
| neuron_rag_retrieval_latency_seconds | Histogram | (none) | Retrieval & ranking latency samples |
| neuron_rag_rank_debug_requests_total | Counter | (none) | Debug history endpoint calls |
| neuron_retrieval_probe_total | Counter | tenant,result | Synthetic probe outcomes |

## Rule Engine
| Metric | Type | Labels | Notes |
| neuron_response_rule_reload_total | Counter | result | Rule file reload outcomes (success|error|skipped) |
| neuron_response_rule_eval_total | Counter | rule_id,result | Match / no_match / error outcomes |
| neuron_response_rule_chain_total | Counter | result | Chaining guard & success results |
| neuron_response_rule_latency_seconds | Histogram | rule_id | Per-rule evaluation latency |

## Cases & Tickets
| neuron_case_total | Gauge | (none) | Active (non-closed) cases |
| neuron_case_status_total | Gauge | status | Lifecycle distribution |
| neuron_case_timeline_events_total | Counter | (none) | Timeline mutations |
| neuron_case_promotions_total | Counter | reason | Promotion triggers |
| neuron_ticket_transitions_total | Counter | status_from,status_to | (legacy; not fully documented) |

## Fusion & Detection
| neuron_fusion_suppression_rate | Gauge | tenant | Recent suppression ratio |
| neuron_fusion_weight_updates_total | Counter | strategy | Weight update events |
| neuron_fusion_temporal_weight | Gauge | tenant | Current temporal weight |
| neuron_retrieval_drift_adjust_total | Counter | outcome | Adjustments & skips |
| neuron_detector_latency_seconds | Histogram | tenant,detector | Detector processing time |
| neuron_anomalies_total | Counter | tenant,detector | Emitted pre-fusion anomalies |

## Governance & Policy
| neuron_governance_composite_signal | Gauge | (none) | Blended governance signal |
| neuron_governance_policy_bypass_total | Counter | reason | Bypass attempts (if emitted) |

## Cardinality Guard
| neuron_cardinality_guard_drops_total | Counter | metric,label | Dropped label expansions due to tenant cardinality limit |

## Startup / Health (Planned)
| neuron_startup_self_test_total | Counter | result | Self-test (pass|fail) aggregate (pending implementation) |

## Contributing
When introducing new metrics:
1. Add definition in `core/metrics.py`.
2. Update snapshot (`tests/metrics_snapshot.txt`) if family is stable.
3. Document in this file with purpose and label rationale.
4. Avoid high-cardinality labels (user_id, raw hash values, free-form text).

