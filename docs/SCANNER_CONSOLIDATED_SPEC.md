# Scanner Pivot Consolidated Strategy & Specification

Version: 0.1-draft (for Claude Opus review)  
Associated Audit Entry: A20 (pivot checkpoint)  
Determinism Pillars Referenced: embedding hash (temporal), artifact hash (proof harness), ontology store hash, ordered event traversal, seeded RNG.

---
## 0. Executive Snapshot
Objective: Provide a deterministic, batch “forensic scanner” path that can (a) demonstrate neuromorphic uplift credibly, (b) enrich anomalies with lightweight knowledge tags, and (c) remain governance‑ready for later promotion without over‑engineering now.  
This document consolidates five strategic option variants, the ASCII architecture spec, knowledge/NLP integration plan, rollback snapshot guidance, and a minimal CLI specification.

Immediate Recommendation (pre‑review): Start with Option O2 (Enriched Temporal + Ontology Scanner) as the *primary* MVP target, while retaining O1 as a rollback simplicity baseline. Defer vector retrieval (O3) until ontology/tag noise rate is measured on real samples.

Success Signals (early):
- < 2 engineer‑days to produce first deterministic anomaly report on a 100k event batch.
- Neuromorphic separation metric (proof harness) demonstrates ≥ X% improvement over baseline (set X=15% provisional) OR latency parity (no degradation).
- Ontology tag precision (manual spot check of 20 anomalies) ≥ 60% “useful or neutral” tags (≤ 40% noise).

---
## 1. Strategic Scanner Options (Five Variants)

Legend:  
Detectors: RS = Rolling Stats baseline, SNN = Neuromorphic scaffold, IF = Isolation Forest (optional), FUS = Weighted fusion.  
Knowledge: KW = keyword tags, ONT = evolving ontology, VEC = vector retrieval, LLM = summarization/extraction.  
Governance: LG = lightweight (hashes + audit), MD = moderate (promotion gates + manifest diff), HG = heavy (signed manifests + policy enforcement).

### O1. Lightweight Forensic Baseline Scanner
Scope: Deterministic batch anomalies using RS (+ optional SNN side channel), KW tagging only.  
Goal: Fastest path to *any* reproducible forensic report.  
Knowledge: CVE/CWE keyword tagger (existing).  
Determinism: Fixed seed; stable ordering by timestamp then tie-break.  
Governance: LG (hash run manifest + A20 anchor).  
Pros: Minimal complexity, fastest delivery, smallest surface for regressions.  
Risks: Limited demonstrable uplift; shallow enrichment may underwhelm stakeholders.  
Exit Criteria to Promote to O2: Demonstrate repeatable run + tag noise analysis baseline.

### O2. Enriched Temporal + Ontology Scanner (RECOMMENDED MVP)
Adds temporal embedding + fusion weighting + ontology growth scaffolding (retain KW).  
Knowledge: KW + normalized ontology store (hash).  
Detectors: RS + SNN + FUS (optionally IF gated by config).  
Governance: MD (manifest of detectors + embedding spec version + ontology hash).  
Pros: Balanced uplift proof (temporal context + neuromorphic) without retrieval complexity.  
Risks: Slightly higher coordination cost (tuner, embedding).  
Key Metrics: Fusion unique contribution ratio, separation metric improvement, tag usefulness rate.  
Upgrade Path: Natural precursor to O3 (can add vector index later without breaking contracts).

### O3. Hybrid Retrieval-Augmented Scanner
Adds vector store (approx nearest neighbor) over embeddings for context & cluster labeling.  
Knowledge: ONT + VEC (embedding index).  
Detectors: Same as O2 (optionally cluster-level anomaly scoring).  
Governance: MD (index hash + compaction log).  
Pros: Better contextual grouping; could reduce analyst triage.  
Risks: Index freshness + drift; added infra dependencies; reproducibility complexity (must snapshot index or recompute deterministically).  
Prereq Stability: Embedding spec version locked + ontology stable ingest pipeline.  
Exit Criteria for O4 Consideration: Demonstrated reduction in duplicate anomaly entries ≥ 20%.

### O4. Adaptive Neuromorphic Live-Replay Scanner
Extends batch with *adaptive replay loops* using neuromorphic threshold calibration on recorded streams.  
Knowledge: ONT + (optional) VEC.  
Detectors: RS + SNN adaptive thresholds + FUS dynamic weight updates (bounded).  
Governance: MD→HG (must log adaptation events with parameter deltas).  
Pros: Strong differentiation (adaptive neuromorphic narrative).  
Risks: Complexity; higher risk of non-determinism unless adaptation logs are fully captured & re-playable.  
Gate: Only after O2 metrics plateau + reliability variance within target band.

### O5. Full Fusion Compliance Scanner
Full governance hardening: signed manifests, policy-driven detector promotion, advanced NLP (LLM summarization + extraction + reasoning).  
Knowledge: ONT + VEC + LLM summarizer/classifier.  
Detectors: All plus potential temporal transformer or advanced SNN variant.  
Governance: HG (cryptographic signing, chain-of-custody).  
Pros: Enterprise-grade trust & rich contextual narratives.  
Risks: Long lead time; high maintenance; risk of LLM hallucination requiring guardrails.  
Only Pursue After: Clear business requirement + validated uplift from earlier stages.

### Option Comparison (Qualitative)
| Option | Time-to-Value | Uplift Proof Strength | Enrichment Depth | Repro Complexity | Recommended Use Case |
|--------|---------------|-----------------------|------------------|------------------|---------------------|
| O1     | Fastest       | Low                   | Low (KW)         | Low              | Initial stake-in-ground |
| O2     | Fast          | Medium                | Medium (Ontology)| Low-Med          | MVP / stakeholder demo |
| O3     | Moderate      | Medium+ (clusters)    | High (Context)   | Medium           | Scaling analyst efficiency |
| O4     | Longer        | High (adaptive)       | High             | High             | Differentiated R&D phase |
| O5     | Longest       | High (comprehensive)  | Very High        | Very High        | Enterprise compliance launch |

---
## 2. ASCII Architecture Specification (Batch Forensic Scanner)

Primary Flow (O2 baseline representation):

```
          +-------------------+        +----------------+        +------------------+        +------------------+
Input --> | Batch Loader /    |  -->   | Normalizer &   |  -->   | Temporal Embed & |  -->   | Detector Suite   |
 (JSONL)  | Iterator (seeded) |        | Schema Validate|        | Feature Builder  |        | (RS / SNN / IF*) |
          +---------+---------+        +-------+--------+        +---------+--------+        +---------+--------+
                    |                           |                             |                        |
                    v                           v                             v                        v
                Ordering &              Missing/Type Coerce            Embedding Hash             Raw Scores
                Stable Sort (ts,id)      Null Safe Defaults            (deterministic)            + metadata
                                                                                                        
                                                                                                        v
                                                                                           +------------+-------------+
                                                                                           | Fusion & Weight Tuner   |
                                                                                           | (deterministic inputs)  |
                                                                                           +------------+------------+
                                                                                                        |
                                                                                                        v
                                                                                           +------------+-------------+
                                                                                           | Ontology / Keyword Tags |
                                                                                           +------------+-------------+
                                                                                                        |
                                                                                                        v
                                                                                           +------------+-------------+
                                                                                           | Report Writer (JSONL)   |
                                                                                           | + Summary Metrics       |
                                                                                           +------------+-------------+
                                                                                                        |
                                                                                                        v
                                                                                           Audit Manifest (hashes)
```

Determinism & Reproducibility Controls:
- Event Ordering: Sort key (timestamp, original_index) stable.
- Randomness: Single RNG seeded at process start (CLI argument `--seed`); passed down; any stochastic detector uses `rng` context.
- Embedding: Stable feature selection list (spec versioned). Hash = SHA256(first16) over canonical JSON (sorted keys, fixed float formatting).
- Ontology: Loaded store file with recorded hash; tagger purely substring -> deterministic.
- Fusion: Weight tuner either disabled for pure determinism or runs in “logged adjustments” mode; all deltas recorded.
- Manifest: JSON manifest includes (code version ref if available), embedding spec version, ontology hash, run parameters, detector enabled set, RNG seed.

Error Handling Contracts:
- Invalid record: Log to stderr (structured) + increment `records_skipped`; never abort batch.
- Detector Failure: Mark detector status degraded; exclude from fusion; add note in summary.
- Hard Failure: Non-zero exit code; partial outputs prefixed with `_FAILED_` to avoid accidental ingestion.

Performance Targets (MVP):
- Throughput: ≥ 50k events/min on commodity laptop for O2 profile.
- Memory: Streaming iteration, constant memory ± embedding window.

---
## 3. Knowledge / NLP Integration Plan

### 3.1 Layered Knowledge Stack
1. Keyword Layer (Now): CVE/CWE substring heuristics (implemented).  
2. Ontology Layer (Short Term): Normalized CVE↔CWE mapping + tag frequency stats; enrichment confidence scoring (frequency-based or heuristic).  
3. Vector Layer (Mid): Embedding space index (FAISS / Annoy). Use *temporal embedding* plus optional derived subspace (e.g., stat deltas).  
4. Hybrid Retrieval (Mid): (Symbolic Filter) → (Vector Approx NN) → (Ontology cross-check) → (Tag Set).  
5. NLP Summarization (Later): Deterministic template + optional LLM post-processor (gated, with guardrails & hallucination filter).  
6. Reasoning / Causal Linking (Future): Graph relationships (sequence adjacency, co-occurrence lift) to produce “anomaly cluster narratives”.

### 3.2 Retrieval Hybrid Design (Future O3+)
Pipeline:
```
Embedding -> Vector Index (topK) -> Candidate Similar Past Events -> Symbolic Filters (severity / source) -> Ontology Cross-Map -> Weighted Tag Score -> Final Tag Set
```

Scoring Fusion (concept):
`score(tag) = w_sym * symbolic_score + w_vec * avg(similarity) + w_freq * log(1 + occurrence_inverse)` (weights tuned offline; deterministic config).

### 3.3 Ontology Evolution Protocol
- Ingest Script (`scripts/ingest_cve_cwe.py`) produces hashed store.
- New ingest adds version number + diff summary; hash chain appended to audit.
- Promotion Rule: Only promote new ontology snapshot if tag noise rate (sampled) ≤ threshold (e.g., 35%).

### 3.4 Quality & Metrics
- Tag Noise Rate: (# tags later deemed irrelevant) / total tags sampled.
- Context Yield: % anomalies with ≥ 1 ontology tag.
- Enrichment Lift: Analyst resolution time delta (needs user study placeholder).
- Retrieval Precision@K (future): fraction of topK neighbors sharing at least one “root cause tag”.

### 3.5 Risk Mitigations
- Determinism: Vector index build uses fixed RNG seed + ordered insertion. Snapshot index file hashed.
- Drift: Schedule periodic re-index; compare cluster stability metrics (e.g., Adjusted Rand vs previous). Gate large drops.
- LLM Hallucination (later): Provide raw evidence chunk boundaries; enforce citation requirement (each claim references record IDs).

---
## 4. Rollback Snapshot Guidance

Purpose: Guarantee ability to revert to pre-pivot operational baseline with cryptographic assurance.

### 4.1 Snapshot Contents
| Component | Description | Artifact |
|-----------|-------------|----------|
| Runtime Params | Current `runtime_params.defaults.json` plus overrides | `artifacts/rollback/params-<ts>.json` |
| Detector Config | Enabled detector list & version strings | manifest field |
| Embedding Spec | Current spec doc hash + version id | manifest field |
| Ontology Store | CVE/CWE store JSON + hash | `artifacts/ontology/store-<hash>.json` |
| Proof Metrics | Last neuromorphic harness summary | `artifacts/proof/summary-<hash>.json` |
| Code Ref | Git commit SHA (if repo) or zipped tree hash | manifest field / archive |

### 4.2 Procedure (Scriptable Outline)
1. Freeze Workspace: ensure clean git state (or archive).  
2. Export Params: copy runtime params + any env overrides into timestamped JSON.  
3. Generate Embedding Canonical Sample: run small deterministic batch; record embedding hash.  
4. Capture Ontology Store: copy with hash in filename.  
5. Run Proof Harness: store output summary JSON (includes its own hash field).  
6. Build Manifest JSON: aggregate hashes + commit + seed; compute manifest hash.  
7. Append Audit Log Entry: reference manifest hash + reason “pre-change snapshot”.  
8. Integrity Verification: Re-run small batch with `--verify-manifest <manifest.json>` (future CLI flag) ensuring recomputed hashes match.  
9. Store Offsite (Optional): push manifest + artifacts to immutable bucket / WORM storage.  

### 4.3 Restoration
1. Retrieve manifest & artifacts package.  
2. Restore code revision (git checkout or unzip).  
3. Restore params & ontology store; verify hash alignment.  

---
## 8. Minimal Phase 1 Scanner CLI (Implemented)

Status: Implemented in A21 (see audit). Provides deterministic batch scanning with dummy exposure plugin and neuromorphic signal placeholder.

Entry Point: `python -m scanner.run_scan` (or module path import)  
Required Args:
- `--input <events.jsonl>` JSONL where each line is an event object (must include at least an `id` and optionally `value`).
- `--out <findings.jsonl>` Output findings JSONL (one JSON object per line) with canonical field ordering.
- `--manifest <manifest.json>` Run manifest summarizing plugin set, neuromorphic signal heuristic value, and scanner param keys.

Optional Args:
- `--plugins <comma_list>` Defaults to `dummy_exposure`.

Determinism Notes:
- Fingerprint: First 16 hex chars of SHA256 over canonical finding core + stable evidence subset.
- Manifest Hash: First 16 hex of SHA256 over canonical manifest core (ts, count, plugins, neu_signal, param_keys).
- Neuromorphic Signal: Heuristic variance/spike placeholder (configurable via `scanner.neuromorphic.*`).

Example Usage:
```
python -m scanner.run_scan \
  --input events.jsonl \
  --out artifacts/scanner/findings.jsonl \
  --manifest artifacts/scanner/manifest.json
```

Sample Finding Line (fields ordered):
```
{"id":"dummy:42","plugin":"dummy_exposure","title":"Value 250 exceeds threshold 100","severity":"HIGH","exploitability":0.7,"score":1.05,"resources":["42"],"evidence":{"threshold":100,"value":250},"tags":["exposure","dummy"],"fingerprint":"abc123def4567890"}
```

Next Steps:
- Integrate ontology tag enrichment (store loader + tagger) into CLI context.
- Add real detector plugins (e.g., open port enumerator, config weakness linter).
- Extend manifest with ontology hash + embedding spec version when integrated.
- Introduce `--seed` flag and deterministic ordering normalization stage.
3. Replace params & ontology store.  
4. Re-run verification batch.  
5. Append audit entry “restored snapshot <manifest_hash>”.

### 4.4 Failure Modes
- Hash Mismatch: Abort restoration; compute differential (file size, timestamp) to detect tampering.  
- Partial Artifact Loss: Reconstruct only if deterministic (e.g., ontology re-ingest) else mark snapshot degraded and escalate.

---
## 5. Minimal Scanner CLI Specification

Goal: Deterministic batch runner producing per-event anomaly outputs + summary metrics + manifest snippet to support reproducibility & comparison.

### 5.1 Core Responsibilities
1. Load events from file(s) (JSONL).  
2. Apply normalization (schema enforcement, missing defaults).  
3. Build temporal embedding window (if enabled).  
4. Execute enabled detectors; gather raw scores.  
5. Perform fusion (if >1 detector).  
6. Tag anomalies (keyword + ontology).  
7. Emit anomaly JSONL (one line per anomaly) + summary metrics JSON + run manifest JSON.  
8. Exit code semantics (0 success, 2 partial degraded, 3 verification mismatch, ≥4 internal error).

### 5.2 CLI Arguments (Draft)
| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--input` | path (repeatable) | required | One or more JSONL event files |
| `--output-dir` | path | `artifacts/scanner/` | Destination for outputs |
| `--seed` | int | 1337 | RNG seed for deterministic ops |
| `--enable-snn` | bool | false | Include neuromorphic detector |
| `--enable-iforest` | bool | false | Include Isolation Forest |
| `--fusion` | bool | true | Enable fusion logic if >1 detector |
| `--embedding` | bool | true | Enable temporal embedding builder |
| `--ontology-store` | path | optional | CVE/CWE store JSON with hash in filename |
| `--max-tags` | int | 5 | Max ontology/keyword tags per anomaly |
| `--score-threshold` | float | 0.7 | Fusion (or single) anomaly score cutoff |
| `--manifest-out` | path | auto inside output | Where to write run manifest |
| `--verify-manifest` | path | None | If provided, verify recomputed hashes vs prior run |
| `--limit` | int | None | Optional cap on number of events processed (debug) |
| `--strict` | bool | false | If true, any detector failure -> nonzero exit (>=4) |

### 5.3 Input Event Contract (Draft Minimal Fields)
| Field | Type | Notes |
|-------|------|-------|
| `timestamp` | int/ISO8601 | Must parse to epoch ms; ordering primary key |
| `id` | string/int | Tie-breaker & traceability |
| `source` | string | Log source/system |
| `message` | string | Free text / may feed keyword tagger |
| Additional numeric features | number | Optional; used by stats baseline |

### 5.4 Output Artifacts
| File | Description |
|------|-------------|
| `anomalies.jsonl` | Per anomaly with: original fields + `scores` map + `fusion_score` + `embedding_hash` (if enabled) + `tags` + `detectors_active` |
| `summary.json` | Metrics: counts, processing time, separation metric (optional if SNN), enabled detectors, tag stats, unique contribution stats |
| `manifest.json` | Seed, detector set, ontology hash, embedding spec version, code ref, parameter hash, run start/end timestamps |
| `verification.json` (optional) | Differences found when `--verify-manifest` supplied |

### 5.5 Metrics (Initial Set)
- `events_total`, `events_skipped`, `anomalies_total`  
- `detector_latencies_ms` (per detector mean / p95)  
- `fusion_unique_ratio`  
- `snn_vs_baseline_separation` (if enabled)  
- `tags_total`, `tags_noise_estimate` (placeholder)  
- `hashes`: embedding spec hash, ontology hash, code ref hash  
- `processing_wall_ms`, `throughput_eps`  

### 5.6 Determinism Notes
- Single-pass streaming ensures stable memory usage.  
- Embedding computed on fixed-size windows (document size in manifest).  
- Float formatting standardized (e.g., 6 decimal places) before hashing.  
- All randomness stems from one seeded RNG instance.  

### 5.7 Implementation Outline (Mapping to Existing Code)
| CLI Layer | Existing / Needed |
|-----------|------------------|
| Argument parsing | NEW (argparse wrapper) |
| Event iteration & normalization | Light NEW module or reuse orchestrator subset |
| Embedding builder | `src/temporal/embedding_builder.py` |
| Detectors | Existing baseline + SNN modules (optionally wrap) |
| Fusion | Existing weighted fusion logic |
| Tagging | `src/ontology/tagger.py` + keyword scan |
| Manifest & hashing | Extend existing hash utilities / add new helper |
| Metrics aggregation | NEW simple accumulator |

### 5.8 Security & Integrity Considerations
- Avoid loading untrusted code: treat ontology store as data only.  
- Hash verification before use (ontology, embedding spec).  
- No network calls (offline mode) to maintain reproducibility.  
- Optional future: sign manifest with offline key.

### 5.9 Sample Invocation (Conceptual)
```
python -m scripts.scanner_cli ^
  --input data/events_batch.jsonl ^
  --seed 42 ^
  --enable-snn --embedding --fusion ^
  --ontology-store artifacts/ontology/store-a1b2c3d4e5f6a7b8.json ^
  --output-dir artifacts/scanner/run_20250904_120000Z
```

---
## 6. Insights & Recommendations
1. Anchor on O2 but implement O1 path behind a single flag toggle for emergency simplification (`--mode baseline`).
2. Defer vector retrieval until (a) ontology tag noise ≤ 35% and (b) at least 2 batches show neuromorphic separation stability (variance < threshold).
3. Invest early in manifest verification (`--verify-manifest`) to preempt subtle drift queries later.
4. Treat tag noise estimation as first “analyst-in-loop” measurement to justify O3.
5. Keep tuner in *observation mode* (log weights, no automatic change) for first two external stakeholder demos to reduce non-determinism accusations.
6. Add a micro “hash summary line” at bottom of anomaly report (human copy/paste) for rapid cross-team reference.

---
## 7. Open Questions (For Claude / Reviewer Feedback)
1. Separation Metric Target: Is ≥15% uplift versus baseline sufficient to justify neuromorphic complexity at MVP? Provide alternative threshold rationale.
2. Ontology Expansion: Should early expansion prioritize depth (more tags per domain) or breadth (cover more domains with fewer tags)?
3. Vector Index Timing: What empirical tag noise or duplicate anomaly threshold should trigger O3 adoption (suggested: duplicate rate > 25%)?
4. Tag Noise Estimation Method: Prefer quick analyst spot-check sample, or automated heuristic (e.g., mutual information with anomaly class) for first pass?
5. Manifest Signing: Is cryptographic signing necessary before external pilot, or can we defer to O5? Risk tolerance input needed.
6. Adaptive Replay (O4): Would stakeholders view adaptive neuromorphic thresholding as core differentiator or “nice future”? Influences resource allocation.
7. LLM Integration: Minimal deterministic templating first, or introduce guarded summarization earlier for stakeholder wow-factor?
8. Performance Constraint: Any strict SLA (e.g., process 1M events under N minutes) we should shape memory/perf engineering around now?

---
## 8. Next Steps (If This Draft Accepted)
1. Implement `scanner_cli.py` per spec (baseline only → add fusion & SNN).  
2. Add `run_manifest.py` helper for hashing + verification.  
3. Create initial ontology noise sampling script.  
4. Integrate separation metric computation into CLI summary when SNN enabled.  
5. Prepare demo batch + record manifest for A21 audit entry.

---
End of Document.
