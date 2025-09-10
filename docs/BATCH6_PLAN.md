# Batch 6 Plan (Preview)

Focus Areas:
1. Advanced Temporal & Transformer Integration
2. Governance Precision Feedback Loop Enhancements
3. External Threat Feed Correlation (real IOC / reputation integration)
4. Adaptive Threshold Runtime Param Surface Expansion
5. Structured Alerting & Notification Pipeline (webhook + email scaffold)

Initial Tasks (proposed):
- [ ] Temporal detector weight governance: expose rolling precision proxy metrics & paramized decay.
- [ ] Transformer embedding anomaly prototype (flow + process sequences) feeding fusion.
- [ ] Threat feed ingestion module (configurable providers, caching, backoff).
- [ ] Alert dispatcher abstraction + basic webhook sink.
- [ ] Runtime param introspection endpoint extension (search & diff views).

Stretch Goals:
- Automated detector threshold suggestion service (analyze BEACON_INTERVAL histogram + lateral distinct growth rates).
- Multi-tenant resource quota enforcement for behavioral maps.
- Enriched anomaly correlation view (timeline + grouping id).

Dependencies / Prereqs:
- Behavioral metrics (added in Batch 5.1) for interval histograms.
- MITRE + threat intel enrichment pipeline (already integrated).

Exit Criteria:
- Fusion incorporates at least one new temporal/transformer signal with documented weight rationale.
- Threat feed ingestion surfaces indicators to enrichment stub (replacing deterministic scoring for supported types).
- Alert dispatcher functional with unit tests (webhook success + retry logic backoff).

## Notes
Feedback welcome before locking exact scope; adjust based on emerging priorities (scaling vs enrichment depth).
