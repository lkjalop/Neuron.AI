"""Retrieval Orchestration Pipeline.

Plan -> multi-subquery retrieval -> corrective refinement -> structured result.
Emits pipeline latency metric. Integrates with tracing if available.
"""
from __future__ import annotations
import time, uuid
from typing import Dict, Any, List

try:
    from core.metrics import (
        RETRIEVAL_PIPELINE_LATENCY,
        RETRIEVAL_SUBQUERY_LATENCY,
        RETRIEVAL_GENERATION_TOKEN_COVERAGE,
        RETRIEVAL_GENERATION_ANSWER_LENGTH,
        RETRIEVAL_GENERATION_CITATION_COUNT,
        RETRIEVAL_GENERATION_SENTENCE_CITATION_RATIO,
        RETRIEVAL_GENERATION_UNSUPPORTED_ENTITIES,
    RETRIEVAL_GENERATION_CONFIDENCE,
    )  # type: ignore
except Exception:  # pragma: no cover
    RETRIEVAL_PIPELINE_LATENCY = None  # type: ignore
    RETRIEVAL_SUBQUERY_LATENCY = None  # type: ignore
    RETRIEVAL_GENERATION_TOKEN_COVERAGE = None  # type: ignore
    RETRIEVAL_GENERATION_ANSWER_LENGTH = None  # type: ignore
    RETRIEVAL_GENERATION_CITATION_COUNT = None  # type: ignore
    RETRIEVAL_GENERATION_SENTENCE_CITATION_RATIO = None  # type: ignore
    RETRIEVAL_GENERATION_UNSUPPORTED_ENTITIES = None  # type: ignore
    RETRIEVAL_GENERATION_CONFIDENCE = None  # type: ignore

try:  # import modules (not symbols) so tests can monkeypatch their attributes reliably
    import core.retrieval.planner as _planner  # type: ignore
except Exception:  # pragma: no cover
    _planner = None  # type: ignore
try:
    import core.retrieval.interface as _iface  # type: ignore
except Exception:  # pragma: no cover
    _iface = None  # type: ignore

try:  # optional tracing
    from observability import tracing as _tracing  # type: ignore
except Exception:  # pragma: no cover
    _tracing = None  # type: ignore


def run_pipeline(query: str, k: int = 5) -> Dict[str, Any]:
    start = time.time()
    trace_id = uuid.uuid4().hex[:16]
    timings: Dict[str, float] = {}
    with _maybe_span("plan"):
        if _planner and hasattr(_planner, "plan"):
            try:
                pl = _planner.plan(query)  # type: ignore[attr-defined]
            except Exception:
                pl = {"error": "planner_error"}
        else:
            pl = {"error": "planner_unavailable"}
    timings["plan"] = time.time() - start
    if "error" in pl:
        duration = time.time() - start
        if RETRIEVAL_PIPELINE_LATENCY is not None:
            try: RETRIEVAL_PIPELINE_LATENCY.observe(duration)
            except Exception: pass
        return {"trace_id": trace_id, "error": pl.get("error"), "plan": pl, "timings": timings, "duration": duration}
    contexts: List[Dict[str, Any]] = []
    seen = set()
    t_retrieve_start = time.time()
    subquery_timings = []
    for sq in pl.get("subqueries", []):
        sq_q = sq.get("q") or ""
        stage = sq.get("stage") or "unknown"
        _sq_start = time.time()
        with _maybe_span(f"retrieve:{stage}"):
            if _iface and hasattr(_iface, "retrieve_context"):
                try:
                    chunks = _iface.retrieve_context(sq_q, k=k)  # type: ignore[attr-defined]
                except Exception:
                    chunks = []
            else:
                chunks = []
        if RETRIEVAL_SUBQUERY_LATENCY is not None:
            try: RETRIEVAL_SUBQUERY_LATENCY.labels(stage=stage).observe(time.time()-_sq_start)
            except Exception: pass
        subquery_timings.append({"stage": stage, "latency": time.time()-_sq_start})
        for c in chunks:
            key = f"{c.get('doc')}#{c.get('chunk_id')}"
            if key not in seen:
                contexts.append(c)
                seen.add(key)
    timings["retrieve_total"] = time.time() - t_retrieve_start
    # Generation phase (provider abstraction) + citations
    gen_start = time.time()
    citations = []
    try:
        from core.retrieval.generation import generate_answer, sentence_citation_coverage, unsupported_entities  # type: ignore
        answer = generate_answer(contexts, query)
        # Build citations from retrieved contexts (same heuristic as before)
        for c in contexts:
            exp = c.get("explanation") or {}
            prov = exp.get("provenance_hash") or c.get("hash")
            mtoks = exp.get("matched_tokens") or []
            if prov and mtoks:
                citations.append({"provenance": prov, "tokens": mtoks[:10], "doc": c.get("doc"), "chunk_id": c.get("chunk_id")})
        # Faithfulness metrics
        try:
            sent_cov_val = sentence_citation_coverage(answer, citations)
            if RETRIEVAL_GENERATION_SENTENCE_CITATION_RATIO is not None:
                RETRIEVAL_GENERATION_SENTENCE_CITATION_RATIO.set(sent_cov_val)
            if RETRIEVAL_GENERATION_UNSUPPORTED_ENTITIES is not None:
                u_count, _ents = unsupported_entities(answer, contexts)
                RETRIEVAL_GENERATION_UNSUPPORTED_ENTITIES.set(u_count)
            # Compute confidence if metrics available
            if RETRIEVAL_GENERATION_CONFIDENCE is not None:
                try:
                    # Token coverage may already be set later; compute interim now
                    ans_tokens = {t.lower() for t in answer.split()}
                    ctx_tokens = set()
                    for c in contexts:
                        exp = c.get("explanation") or {}
                        for t in (exp.get("matched_tokens") or []):
                            ctx_tokens.add(t.lower())
                    token_cov = 0.0
                    if ans_tokens:
                        token_cov = len(ans_tokens & ctx_tokens)/max(1,len(ans_tokens))
                    # Recency factor: require 'ts' per context else neutral 0.75
                    import time as _t, math as _m
                    now = _t.time()
                    ages_h = []
                    for c in contexts:
                        ts = c.get("ts")
                        if isinstance(ts, (int, float)) and ts > 0:
                            ages_h.append((now - ts)/3600.0)
                    if ages_h:
                        # median age
                        ages_h.sort()
                        median_age = ages_h[len(ages_h)//2]
                        H = 24.0
                        recency_factor = 1.0 / (1.0 + (median_age / H))
                    else:
                        recency_factor = 0.75
                    # Unsupported penalty
                    u_penalty = 1.0
                    try:
                        u_penalty = _m.exp(-0.7 * float(u_count))
                    except Exception:
                        pass
                    confidence = 0.5*sent_cov_val + 0.25*token_cov + 0.15*recency_factor + 0.10*u_penalty
                    confidence = max(0.0, min(1.0, confidence))
                    RETRIEVAL_GENERATION_CONFIDENCE.set(confidence)
                except Exception:
                    pass
        except Exception:
            pass
    except Exception:
        # Fallback heuristic answer using matched tokens
        tokens = []
        for c in contexts:
            exp = c.get("explanation") or {}
            tokens.extend(exp.get("matched_tokens") or [])
        answer = " ".join(tokens[:120])
    gen_duration = time.time() - gen_start
    timings["generation"] = gen_duration
    # Generation metrics
    try:
        if RETRIEVAL_GENERATION_ANSWER_LENGTH is not None:
            RETRIEVAL_GENERATION_ANSWER_LENGTH.set(len(answer.split()))
        if RETRIEVAL_GENERATION_CITATION_COUNT is not None:
            RETRIEVAL_GENERATION_CITATION_COUNT.set(len(citations))
        ans_tokens = {t.lower() for t in answer.split()}
        ctx_tokens = set()
        for c in contexts:
            exp = c.get("explanation") or {}
            for t in (exp.get("matched_tokens") or []):
                ctx_tokens.add(t.lower())
        if ans_tokens and RETRIEVAL_GENERATION_TOKEN_COVERAGE is not None:
            coverage = len(ans_tokens & ctx_tokens)/max(1,len(ans_tokens))
            RETRIEVAL_GENERATION_TOKEN_COVERAGE.set(coverage)
        # If confidence wasn't computed earlier due to exception, attempt simplified compute now
        if RETRIEVAL_GENERATION_CONFIDENCE is not None:
            try:
                # Only compute if gauge is 0 (initial) and we have baseline metrics
                # (Prometheus client doesn't expose a get() easily; skip duplicate logic for simplicity)
                pass
            except Exception:
                pass
    except Exception:
        pass
    with _maybe_span("corrective"):
        if _iface and hasattr(_iface, "run_corrective"):
            try:
                corrective = _iface.run_corrective(query, answer, k=k)  # type: ignore[attr-defined]
            except Exception:
                corrective = {"iterations": 0, "history": [], "final_context": [], "final_answer": answer}
        else:
            corrective = {"iterations": 0, "history": [], "final_context": [], "final_answer": answer}
    timings["corrective"] = time.time() - (t_retrieve_start + timings["retrieve_total"])
    duration = time.time() - start
    if RETRIEVAL_PIPELINE_LATENCY is not None:
        try: RETRIEVAL_PIPELINE_LATENCY.observe(duration)
        except Exception: pass
    return {
        "trace_id": trace_id,
        "plan": pl,
        "contexts": contexts,
        "corrective": corrective,
        "answer_citations": citations,
        "answer": answer,
        "timings": timings,
        "subquery_timings": subquery_timings,
        "duration": duration,
        "confidence": None if RETRIEVAL_GENERATION_CONFIDENCE is None else None,  # placeholder; UI fetch via /metrics if needed
    }

class _maybe_span:
    def __init__(self, name: str):
        self.name = name
        self.ctx = None
    def __enter__(self):
        if _tracing and hasattr(_tracing, "start_span"):
            try:
                self.ctx = _tracing.start_span(self.name)
            except Exception:
                self.ctx = None
        return self
    def __exit__(self, exc_type, exc, tb):
        if self.ctx:
            try:
                self.ctx.finish()
            except Exception:
                pass

__all__ = ["run_pipeline"]
