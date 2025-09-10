"""Compositional RAG Planner (Phase C scaffold).

Decomposes complex remediation planning queries into structured sub-queries:
  inventory impact
  exploit evidence
  patch availability
  SLA breach risk

Produces structured JSON contract validated against a lightweight schema.
Metrics emitted via core.metrics (best-effort):
  - RETRIEVAL_COMPOSE_SUBQUERY_TOTAL{stage}
  - RETRIEVAL_COMPOSE_SCHEMA_FAILURE_TOTAL{reason}
  - RETRIEVAL_COMPOSE_LATENCY (overall)

Runtime params (future):
  retrieval.compose.enabled (bool)
  retrieval.compose.max_subqueries (int)
"""
from __future__ import annotations
from typing import Dict, Any, List
import time, json

try:
    from core.metrics import (
        RETRIEVAL_COMPOSE_SUBQUERY_TOTAL,
        RETRIEVAL_COMPOSE_SCHEMA_FAILURE_TOTAL,
        RETRIEVAL_COMPOSE_LATENCY,
    )  # type: ignore
except Exception:  # pragma: no cover
    RETRIEVAL_COMPOSE_SUBQUERY_TOTAL = None  # type: ignore
    RETRIEVAL_COMPOSE_SCHEMA_FAILURE_TOTAL = None  # type: ignore
    RETRIEVAL_COMPOSE_LATENCY = None  # type: ignore

SCHEMA = {
    "type": "object",
    "required": ["query", "subqueries"],
    "properties": {
        "query": {"type": "string"},
        "subqueries": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["stage", "q"],
                "properties": {
                    "stage": {"type": "string", "enum": ["inventory", "exploit", "patch", "sla"]},
                    "q": {"type": "string"},
                },
            },
        },
    },
}


def _validate(output: Dict[str, Any]) -> bool:
    try:
        if not isinstance(output, dict):
            return False
        if not isinstance(output.get("query"), str):
            return False
        subs = output.get("subqueries")
        if not isinstance(subs, list) or not subs:
            return False
        for s in subs:
            if not isinstance(s, dict):
                return False
            if s.get("stage") not in {"inventory", "exploit", "patch", "sla"}:
                return False
            if not isinstance(s.get("q"), str) or not s.get("q"):
                return False
        return True
    except Exception:
        return False


def decompose(query: str) -> Dict[str, Any]:
    """Heuristic decomposition into sub-queries.

    Placeholder using keyword detection; refine with LLM later.
    """
    stages: List[Dict[str, str]] = []
    q_lc = query.lower()
    if any(k in q_lc for k in ("inventory", "asset", "host")):
        stages.append({"stage": "inventory", "q": query + " impacted assets"})
    else:
        stages.append({"stage": "inventory", "q": query + " assets"})
    if any(k in q_lc for k in ("exploit", "kev", "epss")):
        stages.append({"stage": "exploit", "q": query + " exploit evidence"})
    else:
        stages.append({"stage": "exploit", "q": query + " exploit status"})
    if "patch" in q_lc or "fix" in q_lc:
        stages.append({"stage": "patch", "q": query + " patch availability"})
    else:
        stages.append({"stage": "patch", "q": query + " remediation patch"})
    stages.append({"stage": "sla", "q": query + " sla breach risk"})
    return {"query": query, "subqueries": stages}


def plan(query: str) -> Dict[str, Any]:
    start = time.time()
    plan_obj = decompose(query)
    valid = _validate(plan_obj)
    if not valid:
        if RETRIEVAL_COMPOSE_SCHEMA_FAILURE_TOTAL is not None:
            try:
                RETRIEVAL_COMPOSE_SCHEMA_FAILURE_TOTAL.labels(reason="validation").inc()
            except Exception:
                pass
        return {"error": "schema_validation_failed", "raw": plan_obj}
    # Emit subquery metrics
    if RETRIEVAL_COMPOSE_SUBQUERY_TOTAL is not None:
        for s in plan_obj.get("subqueries", []):
            try:
                RETRIEVAL_COMPOSE_SUBQUERY_TOTAL.labels(stage=s.get("stage") or "?").inc()
            except Exception:
                pass
    dur = time.time() - start
    if RETRIEVAL_COMPOSE_LATENCY is not None:
        try:
            RETRIEVAL_COMPOSE_LATENCY.observe(dur)
        except Exception:
            pass
    return plan_obj


def orchestrate(query: str, k: int = 5, corrective_threshold: int = 2) -> Dict[str, Any]:
    """High-level orchestration (experimental).

    Steps:
      1. Plan (decompose)
      2. For each subquery retrieve context (top-k)
      3. Merge contexts (deduplicate by doc#chunk)
      4. Run single corrective refinement pass on concatenated pseudo answer placeholder
    """
    try:
        from core.retrieval.interface import retrieve_context, corrective_refine  # type: ignore
    except Exception:  # pragma: no cover
        return {"error": "interface_missing"}
    pl = plan(query)
    if 'error' in pl:
        return {"plan": pl, "contexts": []}
    contexts = []
    seen = set()
    for sq in pl.get('subqueries', []):
        sq_q = sq.get('q') or ''
        chunks = retrieve_context(sq_q, k=k)
        for c in chunks:
            key = f"{c.get('doc')}#{c.get('chunk_id')}"
            if key not in seen:
                contexts.append(c)
                seen.add(key)
    # Construct naive draft answer (joined matched tokens)
    tokens = []
    for c in contexts:
        exp = c.get('explanation') or {}
        tokens.extend(exp.get('matched_tokens') or [])
    draft_answer = ' '.join(tokens[:100])
    corrective = corrective_refine(query, draft_answer, k=k, threshold=corrective_threshold)
    return {"plan": pl, "contexts": contexts, "corrective": corrective}

__all__ = ["plan", "decompose", "SCHEMA", "orchestrate"]