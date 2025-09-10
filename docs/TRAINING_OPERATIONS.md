# Training & Operations Guide

Target Ramp Time: < 2 hours

## 1. Environment Setup (15 min)
1. Clone repository & create virtualenv.
2. Install dependencies: `pip install -r requirements.txt` (optionally exclude heavy SNN / transformers for lightweight mode).
3. Run API locally: `uvicorn core.main:build_app --factory --reload`.
4. Export `ADMIN_API_KEY=devadmin` for privileged endpoints.

## 2. Core Concepts (10 min)
| Concept | Summary | Key File |
|---------|---------|---------|
| Event Ingestion | Receives JSON events, validates, enqueues or inline detects | `core/main.py` (`/ingest`) |
| Pipeline | Async processing loop performing detectors & fusion | `core/pipeline.py` |
| Detectors | Baseline + SNN + temporal (extensible registry) | `core/detect/` |
| Fusion | Combines detector outputs with suppression heuristics | `core/pipeline.py` (fusion section) |
| Governance Shadow | Non-mutating threshold advice | `core/pipeline.py` (recommendations) |
| IOC / Hunt Buffers | Ring buffers for quick hunting feedback | `core/main.py` |
| Runtime Params | Dynamic tuning surface | `core/runtime_params` (if present) |

## 3. Common Analyst Tasks (25 min)
1. List recent anomalies:
   ```bash
   curl -H "x-api-key: $ADMIN_API_KEY" "http://localhost:8000/anomalies?tenant=acme"
   ```
2. Inspect ingest health:
   ```bash
   curl -H "x-api-key: $ADMIN_API_KEY" http://localhost:8000/ingest/status
   ```
3. View governance shadow recommendations:
   ```bash
   curl -H "x-api-key: $ADMIN_API_KEY" "http://localhost:8000/governance/recommendations?tenant=acme"
   ```
4. Generate performance baseline:
   ```bash
   python scripts/perf_harness.py --base-url http://127.0.0.1:8000 --samples 200 --concurrency 4
   ```
5. Profile hotspot (optional):
   ```bash
   python scripts/profile_run.py --duration 5
   ```

## 4. Runbooks (30 min)
### 4.1 Elevated Ingest Latency
Symptoms: p95 ingest latency > threshold alert.
Steps:
1. Confirm CPU saturation.
2. Run profiler: `python scripts/profile_run.py --duration 10`.
3. If queue depth rising, consider scaling replicas or enabling alt backend.
4. Record mitigation action in incident log.

### 4.2 High Suppression Rate Alert
Steps:
1. Query suppression metrics.
2. Check recent governance shadow suggestions.
3. Evaluate threshold adjustments with risk commentary before applying.

### 4.3 Detector Spike (False Positives)
1. Pull precision proxy metrics (`baseline`, `snn`).
2. If imbalance >5%, create ticket referencing governance suggestion.
3. Tag event samples for later labeling.

### 4.4 IOC Match Surge
1. Inspect `/hunt/ioc_hits` endpoint (if exists) or metrics.
2. Pivot by `ioc_type` and correlate with time window.
3. Draft provisional incident classification.

### 4.5 Queue Backpressure
1. View `INGEST_QUEUE_DEPTH` metric.
2. If persistent growth, enable dual write (future Stage2) or reduce inline detection.
3. Consider batch post processing if implemented.

## 5. Performance Baseline Maintenance (10 min)
1. After meaningful code change affecting ingest or detectors, run harness.
2. Update `artifacts/perf/baseline.json` only if objective improvement.
3. Commit with message `perf: update baseline (p95 -12%)`.
4. CI gating ensures no silent regressions.

## 6. Security & Supply Chain Quick Checks (10 min)
```bash
python scripts/security_baseline.py
python scripts/coverage_report.py --min 75
python scripts/attest_sbom.py --sbom artifacts/security/sbom.json (if args exist)
```
Review delta from dual scanners (after overlap script added).

## 7. Incident Logging Template
```
# Incident <ID>
Start Time: 
Detected By: (alert|metric|manual)
Symptoms: 
Primary Metrics Impacted: 
Root Cause (provisional): 
Mitigations Applied: 
Follow-up Actions: 
Timeline:
  - t0: detection ...
  - t1: mitigation ...
```

## 8. Escalation Matrix (Placeholder)
| Severity | Definition | Target Response | Escalate To |
|----------|------------|-----------------|-------------|
| SEV-1 | Data loss or ingestion halt | 5 min | Engineering Lead |
| SEV-2 | Significant detection gap | 15 min | Detection Owner |
| SEV-3 | Minor latency regression | 60 min | On-call |

## 9. Analyst Ramp Checklist
- [ ] Completed environment setup
- [ ] Queried anomalies & governance recommendations
- [ ] Generated perf baseline
- [ ] Ran profiler once
- [ ] Executed security baseline script
- [ ] Reviewed incident template & escalation matrix

## 10. Glossary
| Term | Definition |
|------|------------|
| Baseline Detector | Statistical anomaly baseline referencing windows |
| SNN | Spiking neural network based anomaly detection (optional heavy) |
| Fusion | Combining multiple detector outputs + suppression logic |
| Governance Shadow | Suggests threshold tuning without applying it |
| Precision Proxy | Synthetic sampling to approximate FP rate |

---
Document version: 1.0
