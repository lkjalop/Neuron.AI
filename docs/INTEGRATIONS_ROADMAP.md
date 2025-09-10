# Integrations Roadmap

Version: 1.0

## Prioritization Principles
1. Coverage of highest-risk telemetry sources.
2. Leverage existing synthetic data pipelines for validation.
3. Maximize detector leverage (shared enrichment across sources).
4. Minimize operational lift (SaaS before self-hosted where possible).

## Phase A (Foundational Internal Sources)
| Connector | Rationale | Sample Payload Source | Status |
|-----------|-----------|-----------------------|--------|
| EDR Stub (generic endpoint events) | Core process / auth telemetry baseline | Synthetic fixture generator | Planned |
| Netflow (summary flows) | Lateral movement & beacon heuristics | Public flow samples / synthetic | Planned |
| DNS Logs | Early C2 + tunneling detection | Synthetic + open malware domains | Planned |
| Enhanced SIEM Ingest (generic JSON) | Unifies ad-hoc event types | Existing test harness | Planned |

## Phase B (High Signal External APIs)
| Connector | Rationale | Enrichment Benefit | Notes |
|-----------|-----------|--------------------|-------|
| Threat Intel Feed (hash/IP/domain) | IOC correlation | Immediate IOC hit amplification | Evaluate licensing |
| Cloud Audit (AWS CloudTrail subset) | Priv escalation / anomalous API use | Governance & anomaly context | Scope minimal subset |
| Identity Provider Events (SSO) | Account compromise patterns | Lateral detection cross-link | Map to existing user model |

## Phase C (Advanced / Niche)
| Connector | Rationale | Added Value | Risk |
|-----------|-----------|-------------|------|
| Container Runtime Events | Runtime attack surface | Process injection / crypto mining | Higher cardinality |
| Kubernetes Audit Logs | Control plane anomaly detection | Governance + drift | Large volume |
| Email Security (phish events) | Cross-channel correlation | Multi-signal correlation | Data sensitivity |

## Behavioral & Network Detector Mapping
| Detector | Source Dependency | MITRE Techniques (Examples) |
|----------|-------------------|-----------------------------|
| Lateral Movement (suspicious remote exec) | EDR + Netflow | T1021, T1077 |
| Persistence (startup mods) | EDR | T1060 |
| Beaconing (interval analysis) | Netflow + DNS | T1071 |
| DNS Tunneling (entropy / length) | DNS Logs | T1572 |

## Data Enrichment Surface
- Reverse DNS / WHOIS (for network artifacts)
- GeoIP (country anomalies)
- Threat intel tagging (confidence score)
- MITRE technique attachment for detection outputs

## Milestone Targets
| Milestone | Connectors Completed | Detectors Active | Enrichment Enabled |
|-----------|----------------------|------------------|-------------------|
| M1 | EDR Stub, DNS | 2 | Basic MITRE tags |
| M2 | + Netflow | 3 | Threat intel tagging |
| M3 | + SIEM Generic | 4 | GeoIP |
| M4 | + Cloud Audit | 5 | Reverse DNS |

## Validation Strategy
1. Synthetic fixture datasets per connector.
2. Replay harness generating predictable anomalies.
3. Precision proxy verifies FP bounds for new detectors.
4. Comparative latency measurement pre/post new connectors.

## Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|-----------|
| Volume spikes (flow logs) | Backpressure, latency | Sharding & batching roadmap |
| Data quality variance | Detector noise | Normalization + schema validation |
| Third-party API outages | Gaps in enrichment | Graceful degrade + caching |

## Exit Criteria for Phase A
- Sample events ingested for each connector via harness.
- At least one synthetic positive per new detector.
- MITRE technique metadata appended to detection output.

---
Document version: 1.0
