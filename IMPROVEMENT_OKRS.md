# Improvement OKRs (Initial Draft)

Timeframe: Q4 2025 (12 weeks)
Baseline Date: 2025-09-07

## Objective 1: Strengthen Core Observability & Governance Transparency
| Key Result | Baseline | Target | Measurement |
|------------|----------|--------|-------------|
| 1.1 95th percentile fusion decision latency | (TBD collect) | <= 40 ms | Perf harness run weekly |
| 1.2 Mapping staleness SNN normalization alerts per week | ad-hoc | <= 1 (non-degraded ops) | Prometheus alert count |
| 1.3 Governance shadow recommendations review SLA | none | 24h median | Audit log timestamps |
| 1.4 Executive composite signal freshness lag | n/a | < 70s | Timestamp diff snapshot |

## Objective 2: Security Baseline & Supply Chain Hygiene
| Key Result | Baseline | Target | Measurement |
|------------|----------|--------|-------------|
| 2.1 High/Critical dependency CVEs (prod image) | ? | 0 | pip-audit + cyclonedx scan |
| 2.2 SAST (ruff+bandit) gated issues (severity >= medium) | untracked | 0 outstanding | CI summary |
| 2.3 SBOM generation latency | manual | < 15s | `security_baseline.py` log |
| 2.4 Secrets committed (detect-secrets baseline delta) | unknown | 0 new | Pre-commit scan diff |

## Objective 3: Performance & Scalability Readiness
| Key Result | Baseline | Target | Measurement |
|------------|----------|--------|-------------|
| 3.1 Sustained ingest throughput (events/sec single instance) | TBD | >= 1500 | Perf harness synthetic load |
| 3.2 Memory footprint steady-state @1k eps | TBD | < 650MB RSS | psutil sampling |
| 3.3 CPU utilization @ target throughput | TBD | < 70% avg | Perf harness stats |
| 3.4 Queue backlog growth under burst (5x) | TBD | clears < 5s | Harness burst scenario |

## Objective 4: Release Engineering & Reproducibility
| Key Result | Baseline | Target | Measurement |
|------------|----------|--------|-------------|
| 4.1 Mean time to cut tagged release (code->artifact) | manual 45m? | < 8m | Script timing |
| 4.2 Changelog completeness (features with entry) | partial | 100% | Release diff script |
| 4.3 Deterministic build hash variance across 3 runs | unknown | 0 differing file hashes | Hash manifest compare |
| 4.4 Manifest / SBOM published with release | partial | 100% | Artifact presence check |

## Objective 5: Analyst & Operator Enablement
| Key Result | Baseline | Target | Measurement |
|------------|----------|--------|-------------|
| 5.1 Time to first anomaly (fresh clone) | ~25m | < 10m | Onboarding dry run |
| 5.2 Docs task coverage (critical runbooks implemented) | ~40% | >= 90% | Checklist scoring |
| 5.3 Mean onboarding quiz score after training module | none | >= 85% | Quiz engine (future) |
| 5.4 Frontend diagnostics usage adoption | none | > 5 sessions/day (internal) | Access logs |

## Objective 6: Detection Quality & Stability
| Key Result | Baseline | Target | Measurement |
|------------|----------|--------|-------------|
| 6.1 Precision proxy delta (SNN vs baseline) | variable | |delta| < 0.05 sustained | Rolling proxy metrics |
| 6.2 Suppression rate guard triggers | ad-hoc | <= 1 / day | Guard counter |
| 6.3 Drift guard false-positive actions | unknown | 0 | Audit action classification |
| 6.4 Autotune suppression adjustments accuracy (post-hoc) | n/a | >= 80% beneficial | Label audit review |

## Objective 7: Extensibility & Integration
| Key Result | Baseline | Target | Measurement |
|------------|----------|--------|-------------|
| 7.1 Pluggable ingestion abstraction landed | none | implemented | Code merge |
| 7.2 Redis ingestion path latency overhead | n/a | < 5% vs in-memory | Perf A/B compare |
| 7.3 External connector stubs documented | partial | >= 5 prioritized | INTEGRATIONS.md count |
| 7.4 MITRE mapping coverage for deployed detections | scaffolding | >= 80% mapped | Mapping report |

---
### Measurement Cadence
- Weekly: Security, performance, detection stability KR snapshots
- Bi-weekly: OKR review adapt thresholds if baseline deviates significantly

### Tooling Plan
- Add `scripts/perf_benchmark.py` (harness) for Objective 3 metrics.
- Add `scripts/security_baseline.py` for Objective 2 KRs (invokes ruff, bandit, pip-audit, cyclonedx, secret scan).
- Add `scripts/release_build.py` for Objective 4 (version bump, manifest, SBOM, changelog append).

### Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|-----------|
| SNN heavy deps slow CI | Longer feedback loop | Optional extras group; lazy import guards (present) |
| False positives in governance guards | Unnecessary disable actions | Add min evidence windows + FP diff confidence band |
| Perf harness diverges from prod patterns | Misleading metrics | Parameterize event shapes / distribution configurable |
| Security scans produce noise | Alert fatigue | Severity filtering + allowlist config |

### Acceptance for End of Quarter
All objectives meet >= 80% of KRs; no critical KR (<50%). Release pipeline demo from clean clone to signed artifact in < 10 minutes.
