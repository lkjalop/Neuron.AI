## SIEM / SOAR Integration Roadmap

Phased plan for integrating external telemetry sources and automated response platforms while preserving governance & model integrity.

### Phase A: Read-Only Ingestion (Low Risk)
Sources: Syslog (RFC5424), CloudTrail export, EDR JSON batch.
Mechanism: Pull adapters (cron fetch) normalize to `Event` schema.
Governance: All external ingest behind allowlist + schema validator.
Metrics: Ingest volume, parse failures, enrichment latency.

### Phase B: Enriched Context & Threat Intel Correlation
Add: IP/Domain reputation (open source), process lineage stitching, basic user/org directory attributes.
Storage: Lightweight Postgres tables + optional vector store (Qdrant) for semantic lookup of past anomaly clusters.
Fusion Impact: Provide additional feature channels (user_risk_score, asset_criticality) to weighted_sum strategy.

### Phase C: Active Temporal Modeling (Transformer Enable Flag)
Prereq: `detection.temporal.enable_transformer` runtime param flipped after A/B gate.
Add sliding sequence buffer per tenant (N=500-1000 events) feeding temporal encoder.
KPIs: Overlap ratio uplift without precision proxy regression >10%.
Fallback: Automatic disable if latency > configured guard or suppression_rate spike.

Implemented scaffolding:
- `core/sequence/buffer.py` (rolling normalized vectors)
- `core/features/registry.py` (canonical feature ordering + vectorization)
- Temporal guard params: `temporal.guard.max_latency_s`, `temporal.guard.max_window`
- Metrics: `neuron_temporal_latency_seconds`, `neuron_temporal_guard_trips_total`, `neuron_temporal_only_anomalies_total`
- Adaptive weight placeholder: `detection.temporal.weight`

### Phase D: Multi-Agent Collaboration (Analyst Assist)
Agents:
1. Detection Analyst Agent – Summarizes anomaly context & proposes triage priority.
2. Threat Hunter Agent – Performs pattern similarity searches (vector retrieval) & MITRE mapping explanation.
3. Firefighter/Responder Agent – Suggests containment actions (never executes directly in this phase).
Inter-Agent Bus: In-memory publish/subscribe (future: Redis streams) with signed message envelopes.
Guardrails: All agent outputs logged & hashed; human approval required for any action escalation.

### Phase E: SOAR Action Orchestration (Controlled Automation)
Scope: Limited to low-impact actions (tagging, ticket creation) with two-person approval for isolation or credential revocation.
Playbooks: Declarative YAML referencing detection conditions + response templates.
Audit: Every executed playbook entry appended to hash-chained audit log (reuse param change mechanism extension).

### Phase F: Closed-Loop Learning & RAG
Add Retrieval-Augmented Generation for enriched analyst summaries:
Sources: Prior incident reports, high-severity anomaly traces, curated threat intel snippets.
Pipeline: Query -> retrieve top-K context -> generate reasoning summary (LLM) -> store explanation ID.
Safety: Deterministic template fallback if retrieval coverage < threshold.

### Data Contracts
Event Core Fields (stable): tenant_id, features{}, timestamp, metadata{}.
Enrichment Extensions: user, process_tree, net_peers, asset_tags (optional keys; presence flagged in schema version metric).

### Success Criteria By Phase
- A: <1% parse failure, stable latency.
- B: +5-10% recall improvement (overlap or SNN unique contributions) without >5% precision proxy regression.
- C: Temporal enabled shows sustained uplift after 10k events.
- D: Analyst time-to-context reduced (qualitative) & zero unauthorized agent actions.
- E: No failed high-severity playbook audits; mean approval latency <5m.
- F: Analyst satisfaction (survey) + decreased duplicate investigation rate.

### Security & Compliance Considerations
- All external connectors operate least-privilege credentials rotated quarterly.
- Hash chain extended to include enrichment source manifest snapshots.
- RAG corpus periodically re-hashed; drift triggers rebuild alert.

### Future Extensions
- Graph-based lateral movement scoring.
- Adaptive suppression regulator (PID loop) to stabilize precision/recall balance.
- Cross-tenant federated anomaly pattern sharing (privacy-preserving).
