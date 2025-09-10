# Forensics Custody Verification

This document explains how the custody chain works for forensics artifacts and how to verify it.

## What is recorded
- Each memory acquisition job produces zero or more `artifacts` in its `job.result.artifacts` list.
- For every artifact, a SHA-256 hash of the JSON-serialized artifact (sorted keys) is appended to `artifacts/forensics/custody.jsonl`.
- Each line contains: `job_id`, `ts`, `hash`, `type`, and `severity`.

## Verify the custody chain
- API: `GET /forensics/custody/verify?job_id=<id>`
- Response fields:
  - `job_id`: The job being verified
  - `artifacts_count`: Number of artifacts present in the current job result
  - `chain_count`: Number of custody entries recorded for this job in the JSONL chain
  - `matches`: Count of matching hashes between the current artifacts and the custody chain
  - `mismatches`: Count of differing hashes across both sets (set symmetric difference)
  - `mismatch_samples`: Up to 5 example hashes that differ

The verification recomputes hashes from the job’s current `result.artifacts` and compares them with entries in `artifacts/forensics/custody.jsonl`. Comparison is order-insensitive and uses set operations.

## Notes & Limitations
- This is a best-effort integrity check intended for demos and dev workflows.
- If artifacts are mutated after initial write, mismatches will be reported.
- The custody file rotates only for jobs list persistence, not for custody chain; rotate externally if needed.
- If the system runs on Windows without optional analyzers available, synthetic artifacts are recorded.

## Troubleshooting
- If the verify endpoint returns `job_not_found`, ensure the job exists via `GET /forensics/jobs/{id}`.
- If `chain_count` is 0, the custody writer may have been disabled or failed; check permissions on `artifacts/forensics/`.
- To view raw entries, open `artifacts/forensics/custody.jsonl`.
