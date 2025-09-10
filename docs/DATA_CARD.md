# Data Card: Synthetic Event Dataset

Version: 0.1

## Summary
Synthetic event stream used for initial detector and fusion evaluation. Provides labeled anomalies approximating diverse system / security signal patterns without real customer data. Enables rapid iteration with reproducibility and no privacy risk.

## Generation Process
- Source Script: `scripts/generate_synthetic_events.py`
- Inputs: Random seeds (optionally fixed), count parameter (default variable), feature distribution definitions embedded in script.
- Event Schema: Aligns with `core.event.Event` fields.
- Each event includes `features` (numeric & categorical convertible to numeric) and optional label `labels.is_anomaly`.

### Feature Families (Typical Examples)
| Feature Group | Examples | Type | Notes |
|---------------|----------|------|-------|
| Process Stats | cpu_usage, mem_usage | float | Simulated % or MB usage distributions |
| Network | bytes_in, bytes_out | int | Basic volume signals |
| Auth | failed_logins_window | int | Rolling window counts |
| System | open_fds, thread_count | int | Resource footprint |
| Custom Security | rare_syscall_ratio | float | Injected anomaly spikes |

Exact feature list may evolve; ensure evaluation artifacts capture commit hash.

## Labeling Logic
- Rules / heuristics in generator introduce anomalies via distribution shifts (mean spikes, variance bursts, rare pattern injections).
- Label binary: `is_anomaly = 1` for injected pattern windows; else 0.
- No multi-class taxonomy yet; roadmap includes type codes (e.g., `exfiltration`, `lateral_movement`).

## Class Balance
- Target initial anomaly rate ~5-12% (tunable). Higher rates accelerate bootstrap stability but deviate from production rarity.
- Future: stratified rare (<1%) anomaly scenario for precision stress testing.

## Data Quality & Limitations
- Lacks temporal correlation across multi-event attack chains.
- No adversarial camouflage or concept drift simulation (handled separately by drift monitor tests).
- Assumes label correctness (no noise model included).
- Lacks tenant heterogeneity; single-tenant evaluations may not surface per-tenant variance issues.

## Ethical / Compliance Considerations
- Synthetic only; no PII or customer operational telemetry.
- Avoids risk of leaking sensitive patterns; safe for open sharing inside engineering org.
- Ensure synthetic descriptors are not misrepresented as real production evidence in external collateral.

## Drift Considerations
- Current dataset static for a given seed; not inherently drifting.
- Drift experiments performed by mixing distributions or shifting parameters mid-stream.
- Planned PSI instrumentation compares live feature distributions vs reference baseline snapshot derived from early stable window.

## Reproducibility Metadata
| Artifact | Description |
|----------|-------------|
| events.jsonl | Primary labeled event list |
| events.manifest.json (future) | Hashes: file length, line count, sha256, generation parameters |
| comparison_metrics.json | Output of `evaluate_models.py` linking to seed, weights, bootstrap config |

## Suggested Extensions
- Multi-tenant generation (varying baseline means / variances) to test isolation.
- Temporal anomaly sequencing (e.g., low-and-slow infiltration => spike) for temporal models.
- Categorical features (process_name category encoding) to test embedding stability.
- Adversarial drift scenarios (slow mean shift) for early PSI sensitivity evaluation.

## Usage Example
```
python scripts/generate_synthetic_events.py --count 1000 > events.jsonl
python scripts/evaluate_models.py events.jsonl --detectors baseline --bootstrap 500
```

## Governance
- Store generated datasets inside `artifacts/dataset/` with timestamped naming when used for formal evaluation.
- Commit hash + seed must accompany any published metric claims.

