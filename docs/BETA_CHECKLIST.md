# Beta Readiness Checklist

Version: 1.0

## 1. Functional Coverage
- [ ] Core ingestion endpoints stable (ingest, status, health)
- [ ] Detection pipeline (baseline + SNN + fusion) enabled in target environment
- [ ] Governance recommendation shadow mode validated
- [ ] IOC matching & hunt buffers producing sample hits

## 2. Quality & Testing
- [ ] Line coverage >= 75% (see artifacts/coverage/coverage.json)
- [ ] Critical modules (ingest, pipeline, fusion, governance) branch points covered
- [ ] Performance harness baseline captured & stored
- [ ] p95 ingest latency within target (< 20ms Stage1)
- [ ] Regression tests for detectors pass consistently

## 3. Security & Supply Chain
- [ ] Security baseline (ruff, bandit, pip-audit) clean or documented exceptions
- [ ] Dual image scan (Trivy + Grype) differences reviewed
- [ ] SBOM generated & attested
- [ ] Secrets scan delta empty (detect-secrets)
- [ ] Image signed (cosign) and verification doc provided

## 4. Observability & Metrics
- [ ] Prometheus scrape operational (metrics endpoint exposed)
- [ ] Alert rules deployed (normalization staleness, suppression rate, ingest lag)
- [ ] Pushgateway (optional) publishing perf metrics
- [ ] Queue depth & backend metrics visible

## 5. Performance & Scalability
- [ ] Baseline JSON stored (artifacts/perf/baseline.json)
- [ ] Hotspot optimization documented with before/after numbers
- [ ] Ingestion backend flag toggled (memory / redis fallback) validated

## 6. Reliability & Operations
- [ ] Runbook for restart & recovery created
- [ ] Backup / export procedure for critical artifacts (db, sbom, perf baseline)
- [ ] Incident response flow (detect -> triage -> escalate) defined
- [ ] On-call rotation placeholder established

## 7. Compliance & Auditability
- [ ] Audit log chain intact (audit/MANIFEST_CHAIN.jsonl up-to-date)
- [ ] Parameter change logs rotation functioning
- [ ] Manifest hash verification documented

## 8. Documentation
- [ ] README updated with latest features & flags
- [ ] SCALING_ARCHITECTURE roadmap reviewed
- [ ] Training & operations guide approved
- [ ] Integrations roadmap published

## 9. Go / No-Go Criteria
All MUST be true:
- [ ] No P1 security vulnerabilities unmitigated
- [ ] No data loss observed in last 72h test window
- [ ] Detection precision proxy windows >= threshold (e.g., 200 synthetic windows)
- [ ] Governance shadow recommendations rational (no runaway diff pattern)
- [ ] p95 latency stable within 10% variance over 24h

## 10. Exit Artifacts
- Coverage report JSON
- Perf baseline
- Latest signed SBOM + attestation
- Release manifest (hash list)
- Changelog entry for beta milestone

---
Status Owner: (assign)
Next Review Date: (set)
