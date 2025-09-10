#!/usr/bin/env python
"""Offline retrieval evaluation harness (Phase A).

Usage (PowerShell):
  python scripts/retrieval_evaluate.py --qa artifacts/retrieval/qa_eval.jsonl --k 5

Computes lightweight metrics without requiring generation:
  - overlap_precision: average coverage from retrieval explanations
  - answer_hit_rate: proportion of questions where any returned chunk explanation tokens include an answer phrase (substring, case-insensitive)
  - grounding_precision: fraction of returned chunks whose doc id is in authoritative doc_ids (if provided)
Emits Prometheus metrics if core.metrics available.

Runtime params that influence behavior (if runtime_params available):
  retrieval.rerank.enabled, retrieval.rerank.top_n, retrieval.grounding.enabled, retrieval.scoring.mode, retrieval.hybrid.embedding_weight

Exit code 0 on success, 1 on any error.
"""
from __future__ import annotations
import argparse, json, sys, pathlib, statistics as stats
from typing import List, Dict, Any

try:
    from core.retrieval.interface import retrieve_context  # type: ignore
except Exception:
    print("[WARN] retrieval interface not available", file=sys.stderr)
    def retrieve_context(question: str, k: int = 5):  # type: ignore
        return []

# Metrics (best-effort)
try:
    from core.metrics import (
        RETRIEVAL_QA_QUESTIONS_TOTAL,
        RETRIEVAL_QA_METRIC,
    )  # type: ignore
except Exception:  # pragma: no cover
    RETRIEVAL_QA_QUESTIONS_TOTAL = None  # type: ignore
    RETRIEVAL_QA_METRIC = None  # type: ignore


def _norm(s: str) -> str:
    return ''.join(ch.lower() for ch in s.strip())


def load_qa(path: pathlib.Path) -> List[Dict[str, Any]]:
    data: List[Dict[str, Any]] = []
    with path.open('r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                data.append(json.loads(line))
            except Exception as e:  # pragma: no cover
                print(f"[WARN] bad QA line: {e}", file=sys.stderr)
    return data


def evaluate(qa: List[Dict[str, Any]], k: int) -> Dict[str, float]:
    total = len(qa)
    if total == 0:
        return {"overlap_precision": 0.0, "answer_hit_rate": 0.0, "grounding_precision": 0.0}
    overlap_coverages = []
    answer_hits = 0
    grounding_hits = 0
    grounding_total = 0
    for ex in qa:
        q = ex.get("question") or ""
        answers = [a for a in ex.get("answers", []) if isinstance(a, str)]
        norm_answers = [_norm(a) for a in answers]
        doc_ids = ex.get("doc_ids") or []
        chunks = retrieve_context(q, k=k)
        # overlap precision proxy
        for c in chunks:
            exp = c.get("explanation") or {}
            cov = exp.get("coverage")
            if isinstance(cov, (int, float)):
                overlap_coverages.append(float(cov))
        # answer hit rate (substring match across explanation tokens placeholder)
        found = False
        pseudo_docs = []
        for c in chunks:
            exp = c.get("explanation") or {}
            toks = exp.get("matched_tokens") or []
            pseudo = ' '.join(toks).lower()
            pseudo_docs.append(pseudo)
            for ans in norm_answers:
                if ans and ans in pseudo:
                    found = True
                    break
            if found:
                break
        if found:
            answer_hits += 1
        # grounding precision: only if authoritative doc ids provided
        if doc_ids:
            grounding_total += len(chunks)
            for c in chunks:
                if c.get("doc") in doc_ids:
                    grounding_hits += 1
        if RETRIEVAL_QA_QUESTIONS_TOTAL is not None:
            try:
                RETRIEVAL_QA_QUESTIONS_TOTAL.labels(status="success").inc()
            except Exception:
                pass
    overlap_precision = stats.mean(overlap_coverages) if overlap_coverages else 0.0
    answer_hit_rate = answer_hits / total if total else 0.0
    grounding_precision = (grounding_hits / grounding_total) if grounding_total else 0.0
    metrics = {
        "overlap_precision": overlap_precision,
        "answer_hit_rate": answer_hit_rate,
        "grounding_precision": grounding_precision,
    }
    if RETRIEVAL_QA_METRIC is not None:
        for k_, v in metrics.items():
            try:
                RETRIEVAL_QA_METRIC.labels(metric=k_).set(v)
            except Exception:
                pass
    return metrics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--qa', type=str, default='artifacts/retrieval/qa_eval.jsonl')
    ap.add_argument('-k', type=int, default=5, help='top-k retrieval per question')
    args = ap.parse_args()
    path = pathlib.Path(args.qa)
    if not path.exists():
        print(f"[ERROR] QA file not found: {path}", file=sys.stderr)
        return 1
    qa = load_qa(path)
    metrics = evaluate(qa, args.k)
    print(json.dumps({"questions": len(qa), **metrics}, indent=2))
    return 0

if __name__ == '__main__':
    sys.exit(main())
