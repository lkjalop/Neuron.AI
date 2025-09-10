# Deterministic Replay Harness

## Purpose
The replay harness provides reproducible validation of governance & retrieval behavior by ingesting a fixed event stream and asserting:
- Governance composite sequence stability (bounded drift across runs)
- Retrieval ordering signature (hash of doc/chunk ordering) consistency
- Optional thresholds for composite monotonicity or variance windows

Implemented in `scripts/replay_harness.py` with a corresponding test `tests/test_replay_harness.py`.

## Key Functions
| Function | Description |
|----------|-------------|
| `load_events(path)` | Loads JSONL events (each line a JSON object) |
| `run_replay(events, client, options)` | Ingests events through `/ingest`, collects governance composite samples & retrieval signatures |
| `analyze(results, thresholds)` | Evaluates drift, retrieval hash stability, and basic statistical properties |

## Invocation (CLI)
```
python scripts/replay_harness.py \
  --events events.jsonl \
  --base-url http://localhost:8000 \
  --max-events 500 \
  --composite-max-delta 0.25 \
  --retrieval-hash expected_hash_here
```
If `--retrieval-hash` omitted, the script prints the observed hash (use it as future expected baseline).

## Output Structure
```
{
  "count": <events_ingested>,
  "composite_samples": [0.42, 0.44, ...],
  "composite_stats": {"min":..., "max":..., "mean":...},
  "retrieval_signature": "<hex>",
  "assertions": {"composite_drift_ok": true, "retrieval_match": true}
}
```

## Threshold Parameters
(Not all provided via CLI yet; extend as needed.)
| Concept | Description | Default Behavior |
|---------|-------------|------------------|
| Composite Max Delta | Max (max-min) allowed before flag | 0.3 (example) |
| Retrieval Signature | Stable ordering hash | Provided / compared |
| Sample Count Floor | Minimum samples before asserting stability | Implicit (>=5) |

## Extending Assertions
Add new validation in `analyze` (e.g., ensure no >X consecutive flat composite points if expecting adaptation). Keep fast and side-effect free.

## Test (`tests/test_replay_harness.py`)
Unit test exercises harness with a small synthetic subset, ensuring:
- Harness runs without exceptions even if real events file missing
- Composite sample list is produced (may be empty if governance not yet generating values)

## Governance Integration
The harness indirectly exercises weight governor logic since composite calculations occur during pipeline operation. Track temporal weight adjustments by parsing `audit/AUDIT_LOG.md` after replay if deeper validation needed.

## Recommended Workflow
1. Capture representative `events.jsonl` from staging or synthetic generator.
2. Run harness against current main branch to establish baseline signatures.
3. After algorithm or parameter changes, rerun and compare.
4. Fail CI if composite drift or retrieval signature deviates beyond risk tolerance.

## Future Enhancements
- Add quantile band comparison vs stored goldens (`artifacts/replay_baseline.json`).
- Integrate precision proxy metrics into assertion set.
- Multi-tenant parallel replay streams.
- Emulator for synthetic exposure changes to test composite adaptation triggers.
