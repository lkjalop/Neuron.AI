# Development & Invocation Guide (Windows / PowerShell)

This document captures quick, repeatable commands for working with the Neuron codebase on Windows using PowerShell.

## Environment Setup

1. Create / activate virtual environment (if not already):
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
2. Install core + test dependencies (lightweight):
```
python -m pip install -r requirements.txt
python -m pip install -r requirements-test.txt
```

## Running Tests Reliably

Always ensure `src` is on `PYTHONPATH`. Easiest method: invoke modules with `-m` from repo root (PowerShell style):
```
# Single test
python -m pytest tests/test_tickets_phase6.py::test_ticket_transition_and_metrics -q

# All tests
python -m pytest -q
```
If you run ad‑hoc scripts, prepend `src`:
```
$env:PYTHONPATH = "$(Resolve-Path src)"; python scripts/some_tool.py
```
Or inline per command:
```
PYTHONPATH=src python ticket_metric_check.py   # (Git Bash)
$env:PYTHONPATH="src"; python ticket_metric_check.py  # (PowerShell)
```

## Metrics Scrape Checks
```
python -c "import sys, pathlib; sys.path.insert(0,str(pathlib.Path('src').resolve())); from prometheus_client import generate_latest; from core.main import app; from starlette.testclient import TestClient; print(generate_latest().decode()[:500])"
```

## Disabling Auto Pipeline Initialization
Set before import if you want a bare app:
```
$env:NEURON_DISABLE_AUTO_PIPELINE = '1'; python -m pytest tests/test_metrics_integrity.py::test_metrics_monotonic_and_histogram_presence -q
```

## Common Pitfalls
- Missing `core` import: ensure you are in repository root and use `python -m` or set `PYTHONPATH`.
- PowerShell here-doc syntax differs from bash; prefer multiple `;` separated one-liners instead of `<<EOF`.
- Long `python -c` chains: keep them short; create a temporary script for complex diagnostics.

## FastAPI Local Run (dev)
```
uvicorn core.main:app --reload --port 8000
```

## Lint / Format (if added later)
Placeholder; adopt `ruff` or `black` as needed.

---
Generated to standardize local dev workflows.

## Metrics Audit

Run the metrics audit script to check for duplicate, colliding, orphaned, or unused metric families:

```powershell
python scripts/metrics_audit.py --pretty
```

Fail build on duplicates & collisions (baseline gate):

```powershell
python scripts/metrics_audit.py --fail-on duplicates,collisions
```

Stricter enforcement including orphan & unused:

```powershell
python scripts/metrics_audit.py --fail-on duplicates,collisions,orphan,unused
```

Fields:
- duplicates: multiple definitions of the same family in core.metrics
- collisions: different collector objects share the same name
- orphan_registry: registered neuron_ metrics not defined in core.metrics
- unused_defined: defined but not currently registered (dead or not imported)

Integrate early in CI before running tests to catch regressions.

### Strict Mode Shortcut

Instead of enumerating categories, you can now run:

```powershell
python scripts/metrics_audit.py --strict --pretty
```

This fails (exit code 1) on any anomaly: duplicates, collisions, orphan, or unused families.

GitHub Actions example:

```yaml
- name: Metrics audit
	run: python scripts/metrics_audit.py --strict --pretty
```

## Contract Regression Tests

The test file `tests/test_contract_core.py` exercises foundational API surface to prevent accidental removal or shape change. Covered endpoints:

- `/metrics`
- `/ioc` (POST + GET)
- `/hunt/query`
- `/fusion/weights/update`
- `/snn/toggle`
- `/fusion/decisions/recent`
- `/governance/signal`
- `/diagnostics/config`
- `/retrieval/pipeline`
- `/retrieval/hunt`
- `/query/nlp`
- `/dashboard/executive`
- `/rag/sync` (optional; tolerated 404)

To run just the contract suite:

```powershell
python -m pytest tests/test_contract_core.py -q
```

Add new baseline endpoints here so CI enforces their continued availability.

### Newly Added Observability & Intelligence Endpoints (Batch 1 / 2A)

Endpoints introduced for pattern TTL/eviction, temporal feature buffering, and artifact correlation:

- `POST /memory/patterns` {pattern, ttl_s?, tags?} -> {created}
- `GET /memory/patterns` (q?, limit?) -> {items, count}
- `GET /memory/patterns/stats` -> {count, last_added_ts, usage, max}
- `POST /memory/patterns/match` {blob} -> {matched, count}
- `POST /temporal/buffer/ingest` {tenant, features:{...}} -> {status, tenant, size}
- `GET /temporal/buffer/status` (tenant?) -> {tenants:{tenant:{size,capacity,retention_s,ready}}}
- `POST /memory/artifact/correlate` {a,b} -> {score, outcome}

### New Metrics Families

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| neuron_memory_pattern_evictions_total | Counter | reason | Evictions (ttl|capacity|prune) from memory pattern store |
| neuron_temporal_buffer_size | Gauge | tenant | Current temporal buffer size per tenant |
| neuron_temporal_buffer_prunes_total | Counter | tenant,reason | Temporal buffer prune events (retention|capacity) |
| neuron_temporal_buffer_ready | Gauge | tenant | 1 if buffer size >= readiness threshold |
| neuron_memory_artifact_correlation_total | Counter | outcome | Correlation scoring attempts by outcome (high|medium|low|error) |

### Contract Test Expansion

`tests/test_contract_core.py` now validates the new endpoints above (excluding optional ones) with minimal shape assertions. Add any future critical surfaces here to guard against regressions.

### Correlation Scoring Heuristic
Jaccard similarity over token sets: outcome thresholds high>=0.66, medium>=0.33 else low. Adjust thresholds or introduce learned weighting in future phases.

## Retrieval & RAG Enhancements

### Ranking Debug Endpoint
`GET /retrieval/rank/debug?limit=N` returns the most recent ranked retrieval executions (bounded ring buffer). Fields per item: `ts`, `query`, `docs` (with scoring adjustments), `duration_ms`. Metric: `neuron_rag_rank_debug_requests_total`.

### Embedding Cache Observability
Counters: `neuron_rag_embedding_cache_hits_total`, `neuron_rag_embedding_cache_misses_total`, `neuron_rag_embedding_cache_evictions_total{reason}`. Use two identical retrieval calls to validate miss->hit progression in tests.

### Memory Artifact Linking
Artifacts attached to cases (and optionally tickets) create link records queryable via `GET /memory/{artifact_id}/links`. Metric: `neuron_memory_artifact_link_total{link_type}` (values: `artifact_case`, `artifact_ticket`). Used for future graph enrichment & retrieval reranking.

### Synthetic Retrieval Probes
Background loop issues periodic synthetic queries per tenant capturing `neuron_retrieval_probe_total{tenant,result}` and latency in `neuron_rag_retrieval_latency_seconds`. Deterministic single-cycle helper `_run_retrieval_probe_once()` supports unit tests without sleep-based flakiness.

## Rule DSL Chaining (Summary)
Rules can reference another rule via `next`. Guardrails:
- Loop detection -> `loop_detected`
- Depth limit -> `depth_exceeded`
Metrics: `neuron_response_rule_chain_total{result}`, `neuron_response_rule_latency_seconds{rule_id}`, and reload outcomes in `neuron_response_rule_reload_total{result}`. Full details: `docs/RULES_CHAINING.md`.

## Chunk Indexing Pipeline (Overview)
The chunk indexing pipeline converts raw source documents (policy text, KB entries, reports) into retrievable embedding chunks consumed by `/retrieval/pipeline`, `/retrieval/hunt`, and `chat` endpoints.

Stages:
1. Ingest & Normalization: assign stable `doc_id`, light cleaning.
2. Segmentation / Chunking: sentence+token greedy window (~512 tokens) with ~50 token overlap.
3. Pre-Filter & Dedup: drop empty or duplicate hash segments (near-dup shingle planned).
4. Embedding & Caching: deterministic pseudo embedding + LRU/TTL cache (`_EMBED_CACHE`) with metrics (`neuron_rag_embedding_cache_*`).
5. Ranking Prep: rank explanations stored in `_RETRIEVAL_RANK_HISTORY` powering `/retrieval/rank/debug`.
6. Probe Validation: `_retrieval_probe_loop` issues synthetic queries -> `neuron_retrieval_probe_total{tenant,result}` + latency samples.
7. Adaptive Signals (planned): drift-based temporal weight nudge & adaptive TTL toggle.

Validation / Error Codes:
- 400: malformed body (`invalid_body`, `documents_must_list`, `candidates_must_list`).
- 501: unsupported experimental mode (`mode_not_supported`).
- 503: disabled via env (`RETRIEVAL_PIPELINE_DISABLED`, `RETRIEVAL_HUNT_DISABLED`).

Traceability: each retrieval response now emits `trace_id` plus `correlation_id` (if middleware injected) to assist cross-request correlation.

Future Enhancements:
- Persisted ANN index (Faiss/HNSW) behind feature flag.
- On-disk chunk manifest w/ checksum + integrity metric.
- Governance label-based chunk visibility filtering layer.

