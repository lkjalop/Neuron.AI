# Retrieval Evaluation Harness (Phase A)

This document describes the offline evaluation harness for Neuron retrieval.

## Labeled QA Set
Store a small JSONL at `artifacts/retrieval/qa_eval.jsonl` with schema:
```
{"id": "Q1", "question": "What is the SLA breach threshold?", "answers": ["30 days", "thirty days"], "doc_ids": ["COMPLIANCE_TRACK.md"]}
```
Fields:
- `question`: Natural language query.
- `answers`: List of acceptable normalized answer spans (case-insensitive match heuristic) or canonical phrases.
- `doc_ids`: (Optional) authoritative source documents (for grounding precision).

## Running Evaluation
A future script `scripts/retrieval_evaluate.py` (placeholder) will:
1. Load QA examples.
2. For each question call `retrieve_context(question, k=K)`.
3. Derive metrics:
   - overlap_precision: proxy from retrieval explanation coverage (avg).
   - answer_hit_rate: proportion where any candidate chunk contains an answer string (substring match placeholder).
   - grounding_precision: fraction of returned chunks whose `doc` is in authoritative `doc_ids` (if provided).
4. Emit Prometheus gauges:
   - `neuron_retrieval_qa_metric_score{metric="overlap_precision"}`
   - `...{metric="answer_hit_rate"}`
   - `...{metric="grounding_precision"}`
5. Count processed vs errors in `neuron_retrieval_qa_questions_total{status}`.

## Runtime Parameters
| Param | Purpose | Default |
|-------|---------|---------|
| `retrieval.rerank.enabled` | Enable cross-encoder re-ranking | 0 |
| `retrieval.rerank.top_n` | Candidate top-N before re-ranking | 50 |
| `retrieval.rerank.model` | Override cross-encoder model name | cross-encoder/ms-marco-MiniLM-L-6-v2 |
| `retrieval.grounding.enabled` | Attach grounding span metadata | 0 |
| `retrieval.metrics.enable` | Allow retrieval metrics emission | 1 |
| `retrieval.scoring.mode` | keyword | keyword |
| `retrieval.hybrid.embedding_weight` | Hybrid IDF weight (0..1) | 0.3 |
| `retrieval.rerank.corrective.threshold` | Unsupported token threshold to trigger refinement | 2 |
| `retrieval.compose.enabled` | Enable compositional planner orchestration | 0 |
| `retrieval.pipeline.enabled` | Enable end-to-end pipeline endpoint `/retrieval/pipeline` | 1 |
| `retrieval.persist_text` | Persist full chunk text for provenance & generation | 0 |
| `retrieval.generation.enabled` | Enable model answer generation (vs heuristic) | 0 |
| `retrieval.generation.provider` | Generation provider (`hf_local`, `ollama`) | hf_local |
| `retrieval.generation.model` | HF model name (seq2seq) | google/flan-t5-small |
| `retrieval.retention.enabled` | Enable background retention pruning loop | 1 |
| `retrieval.retention.max_rows` | Max rows to retain (row-cap pruning) | 50000 |
| `retrieval.retention.max_age_hours` | Max age (hours) before purge; 0 disables age prune | 168 |
| `retrieval.retention.interval_s` | Retention loop interval seconds | 3600 |
| `retrieval.generation.warmup_on_start` | Perform async model warmup after startup | 0 |

## Grounding Metadata
When enabled (`retrieval.grounding.enabled`): each returned record may include:
```
"grounding": {
  "doc": "COMPLIANCE_TRACK.md",
  "chunk_id": 12,
  "spans": [ {"start":0, "end":5, "token":"patch"}, ... ]
}
```
Spans are placeholder token offsets over a pseudo concatenated token string (will evolve to real char offsets when raw chunk text accessible). Use spans to highlight provenance in UI and to audit unsupported answer segments.

## Roadmap
Near-term improvements:
- True character span extraction using stored chunk text.
- RAGAS integration for answer faithfulness & context relevance (requires generation step integration).
- Normalization pipeline for numeric and CVE entity matching.
- Confidence interval estimation over evaluation metrics (bootstrap).

## Corrective Loop (Preview)
Phase B introduces a critic that will:
- Detect CVE IDs in answers absent from retrieved context.
- Detect numeric divergences (e.g., 30 vs 90 days) for SLA metrics.
- Trigger refined retrieval with expanded synonyms if violations exceed threshold.
Metrics added: `neuron_retrieval_corrective_iterations_total`, `neuron_retrieval_corrective_accept_ratio`.

## Orchestration Pipeline
The orchestration layer (`core.retrieval.orchestrator.run_pipeline`) executes:
1. Planning (subquery decomposition) via `planner.plan`.
2. Multi-subquery retrieval (deduplicated contexts) with per-subquery top-K.
3. Pseudo answer synthesis (token heuristic) and corrective refinement loop (`run_corrective`).

Endpoint: `POST /retrieval/pipeline` (predict API key auth) body:
```
{ "query": "<string>", "k": 5 }
```
Returns JSON with fields: `trace_id`, `plan`, `contexts`, `corrective`, `timings`, `duration`.

Runtime gating: disabled when `retrieval.pipeline.enabled` falsy (returns 503).

### Pipeline Metrics
- `neuron_retrieval_pipeline_latency_seconds` (histogram) end-to-end latency.
- `neuron_retrieval_corrective_iterations_total` (counter) total refinement iterations.
- `neuron_retrieval_corrective_accept_ratio` (gauge or summary) acceptance ratio of refinements.
- `neuron_retrieval_rerank_model_load_latency_seconds` (hist) re-ranker model load.
- `neuron_retrieval_grounding_span_coverage_ratio` (gauge) average grounding span coverage.

### Future Enhancements
- Generation step (`generate_answer`) to replace heuristic token concat.
- Faithfulness / answer similarity scoring (RAGAS) instrumentation.
- Per-subquery latency breakdown panel in Grafana.

## Generation & Faithfulness (Phase B Preview Implemented)

When `retrieval.generation.enabled` is set truthy the pipeline will invoke a provider-backed answer synthesis stage.

Providers:
1. `hf_local`: Lazy loads a seq2seq model (default `google/flan-t5-small`) via `transformers`. Single-process in-memory cache; first request pays load latency (consider warmup).
- Warmup: Trigger proactively via `POST /retrieval/generation/warmup` (admin key auth) or set `retrieval.generation.warmup_on_start=1` to schedule an async warmup shortly after process start. Emits `neuron_retrieval_generation_warmup_latency_seconds` histogram.
2. `ollama`: Calls a local Ollama HTTP endpoint (expects `OLLAMA_BASE_URL` env; simple `/api/generate` JSON contract). Fallbacks to heuristic if error.
3. Heuristic fallback: If generation disabled or provider errors, a naive token concatenation heuristic (original behavior) is used.

Returned Response Additions (when enabled):
- `answer`: Generated answer text.
- `answer_citations`: List of chunk doc IDs used (for UI provenance panel).
- `subquery_timings`: Per-subquery retrieval latency breakdown (array of floats seconds).
- `timings.generation`: Generation stage latency.

Faithfulness Proxy Metrics:
- `neuron_retrieval_generation_sentence_citation_ratio` (gauge) – fraction of answer sentences that have at least one citation reference (proxy for grounding completeness). Computation: split answer into sentences; count those containing any cited document marker or heuristic link in citation scaffold vs total.
- `neuron_retrieval_generation_unsupported_entities_total` (counter) – incremented by number of simple entity tokens (e.g., CVE-like patterns / numerics above threshold) not found in retrieved context. Current heuristic implementation; will evolve with richer NER and RAGAS integration.
- `neuron_retrieval_generation_token_coverage_ratio` (gauge) – ratio of unique answer tokens present in context (existing prior metric).
- `neuron_retrieval_generation_citation_count` (gauge/counter depending on implementation) – number of citations collected.

Usage Notes:
- Enable full text persistence (`retrieval.persist_text=1`) to improve future span-level faithfulness audits and to allow more expressive prompts.
- Model size trade-off: Larger models increase latency; consider setting a warmup call after startup.
- Planned: RAGAS metrics for answer relevance, faithfulness, context precision once dependency footprint agreed.

## Retention Policy

Background task (enabled when `retrieval.retention.enabled=1`) periodically prunes the `retrieval_chunks` SQLite table to manage disk footprint and stale context risk.

Pruning Strategy (executed each interval):
1. Age Prune: Delete rows where `created_ts < now - max_age_hours*3600` when `max_age_hours > 0`.
2. Capacity Prune: If remaining rows exceed `max_rows`, delete oldest rows (ascending `created_ts`) until under cap.

Runtime Params Recap:
- `retrieval.retention.max_rows`: Hard cap controlling storage growth.
- `retrieval.retention.max_age_hours`: Temporal freshness bound (set 0 to disable age based pruning).
- `retrieval.retention.interval_s`: Sleep between pruning passes (default 3600s). Lower for aggressive environments.
- `retrieval.retention.enabled`: Disable to suspend pruning (e.g., forensic snapshot phase).

Metrics Emitted:
- `neuron_retrieval_retention_purged_total{reason="age|rows"}` (counter) – rows removed by reason.
- `neuron_retrieval_chunks_rows` (gauge) – current row count post-prune.
- `neuron_retrieval_chunk_text_bytes_total` (gauge) – total length aggregate for persisted chunk text (proxy for disk utilization when using inline blob storage).

Operational Guidance:
- Set `max_rows` proportionally to expected document volume and shard count; start conservative (e.g., 50k) and tune via Grafana growth rate panel.
- For high-churn sources, reduce `max_age_hours` to evict stale compliance policies or superseded advisories sooner.
- Disable retention only for short investigative windows; otherwise risk unbounded growth / degraded relevance.

Failure Modes & Safeguards:
- If pruning encounters an exception it fails silently (best-effort) and retries next interval.
- Table is created if missing (idempotent) to avoid startup ordering issues.
- Metrics emission is guarded; absence of metrics implies retention import/registration failure (check logs).

## Observability Additions

Pipeline response now includes per-subquery timing array and generation stage latency enabling a Grafana waterfall visualization. Coupled with retention gauges you can correlate answer latency spikes with storage growth or pruning frequency.

## Roadmap (Extended)
- Integrate RAGAS for semantic faithfulness & context recall metrics.
- Add per-chunk citation span offsets leveraging persisted text for UI highlighting.
- Adaptive retention (dynamic max_rows based on disk pressure / growth slope).
- Multi-tenant isolation: per-tenant caps and metrics labels.

