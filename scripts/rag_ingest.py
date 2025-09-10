"""Lightweight RAG ingestion scaffold (A17 + hybrid scoring).

Enhancements over A16 baseline:
 - Runtime-parameter driven chunk sizing & overlap (retrieval.chunk_size / overlap)
 - Per-chunk SHA256 hash for provenance (optional flag to persist)
 - Manifest + index JSON artifact emission under artifacts/retrieval/
 - Explanation metadata: matched tokens, overlap counts (& hybrid components when enabled)
 - Hybrid scoring IMPLEMENTED (keyword coverage + simple IDF‑weighted coverage) when
   retrieval.scoring.mode == 'hybrid'. Composite score:

       composite = (1 - w) * coverage + w * idf_coverage

   where w = retrieval.hybrid.embedding_weight (0..1),
         coverage = overlap / |query_tokens|,
         idf_coverage = sum(idf(t) for matched t) / sum(idf(t) for all query t),
         idf(t) = 1 + ln( N / (1 + df(t)) ) with N = total chunks, df = chunk frequency for token.

Usage examples:
    python scripts/rag_ingest.py --docs docs/SOC_IFOREST_OPERATIONS.md --query "extreme-value heuristic"
    python scripts/rag_ingest.py --docs docs/*.md --query "temporal residual variance" --top_k 5
"""
from __future__ import annotations
import argparse, pathlib, re, json, hashlib, time, glob
from typing import List, Dict, Tuple, Any
import math

try:  # Lazy import so script can run stand-alone
    from config import runtime_params
except Exception:  # pragma: no cover
    runtime_params = None  # type: ignore

DEFAULT_CHUNK_SIZE = 800  # characters
DEFAULT_OVERLAP = 80
TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]+")


def get_runtime_param(name: str, fallback: int | float | bool | str):  # helper to avoid repeated guards
    if runtime_params is None:
        return fallback
    val = runtime_params.get_param(name)  # type: ignore[attr-defined]
    return val if val is not None else fallback


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    chunks: List[str] = []
    if chunk_size <= 0:
        return [text]
    step = max(1, chunk_size - max(0, overlap))
    for i in range(0, len(text), step):
        chunks.append(text[i:i+chunk_size])
    return chunks


def tokenize(s: str) -> List[str]:
    return [t.lower() for t in TOKEN_RE.findall(s)]


def build_index(files: List[pathlib.Path]) -> Tuple[Dict[str, List[Tuple[str, int, str]]], Dict[str, List[str]], List[Dict[str, Any]]]:
    chunk_size = int(get_runtime_param("retrieval.chunk_size", DEFAULT_CHUNK_SIZE))
    overlap = int(get_runtime_param("retrieval.chunk_overlap", DEFAULT_OVERLAP))
    index: Dict[str, List[Tuple[str, int, str]]] = {}
    doc_chunks: Dict[str, List[str]] = {}
    manifest: List[Dict[str, Any]] = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        chunks = chunk_text(text, chunk_size, overlap)
        doc_chunks[f.name] = chunks
        for cid, ch in enumerate(chunks):
            toks = set(tokenize(ch))
            ch_bytes = ch.encode("utf-8")
            ch_hash = hashlib.sha256(ch_bytes).hexdigest()
            manifest.append({
                "doc": f.name,
                "chunk_id": cid,
                "hash": ch_hash,
                "length": len(ch),
                "tokens": len(toks),
            })
            for tok in toks:
                index.setdefault(tok, []).append((f.name, cid, ch))
    return index, doc_chunks, manifest


# Backward compatibility shim for older tests expecting a 2-tuple (index, doc_chunks)
def build_index_legacy(files: List[pathlib.Path]):  # pragma: no cover - thin wrapper
    idx, chunks, _manifest = build_index(files)
    return idx, chunks


def retrieve(index, query: str, top_k: int = 3, explanations: bool = True) -> List[Dict[str, Any]]:
    """Retrieve chunks for query.

    Keyword mode: score = raw token overlap count.
    Hybrid mode:  score = composite as defined in module docstring.
    """
    q_tokens_list = tokenize(query)
    q_tokens = set(q_tokens_list)
    if not q_tokens:
        return []
    scores: Dict[Tuple[str,int], int] = {}
    matched_tokens: Dict[Tuple[str,int], List[str]] = {}
    for qt in q_tokens:
        for rec in index.get(qt, []):
            key = (rec[0], rec[1])
            scores[key] = scores.get(key, 0) + 1
            matched_tokens.setdefault(key, []).append(qt)

    # Determine scoring mode & weight
    mode = str(get_runtime_param("retrieval.scoring.mode", "keyword"))
    weight = float(get_runtime_param("retrieval.hybrid.embedding_weight", 0.3))
    weight = max(0.0, min(1.0, weight))

    # Pre-compute IDF if needed
    idf: Dict[str, float] = {}
    total_chunks_est = 0
    if mode == "hybrid":
        # total chunks = unique (doc,cid) in index postings; approximate via manifest length would be better
        seen_pairs = set()
        for postings in index.values():
            for doc, cid, _text in postings:
                seen_pairs.add((doc, cid))
        total_chunks_est = max(1, len(seen_pairs))
        for tok, postings in index.items():
            # df = number of distinct chunks containing token
            chunk_ids = {(d, c) for (d, c, _t) in postings}
            df = len(chunk_ids)
            idf[tok] = 1.0 + math.log(total_chunks_est / (1 + df))

    # Rank candidates
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k*4]  # widen pre-cut for hybrid adjustment

    # Build flat list for text lookup
    posting_lists = []
    for t in q_tokens:
        lst = index.get(t)
        if lst:
            posting_lists.append(lst)
    flat = [rec for pl in posting_lists for rec in pl]

    out: List[Dict[str, Any]] = []
    scored_entries: List[Tuple[float, Dict[str, Any]]] = []

    # Precompute query IDF denominator for hybrid
    if mode == "hybrid" and idf:
        query_idf_total = sum(idf.get(t, 0.0) for t in q_tokens)
        if query_idf_total <= 0:
            query_idf_total = 1.0
    else:
        query_idf_total = 1.0

    for (doc, cid), overlap in ranked:
        text = None
        for rec in flat:
            if rec[0] == doc and rec[1] == cid:
                text = rec[2]
                break
        if text is None:
            continue
        coverage = overlap / max(1, len(q_tokens))
        if mode == "hybrid" and idf:
            toks = matched_tokens.get((doc, cid), [])
            idf_cov = sum(idf.get(t, 0.0) for t in toks) / query_idf_total
            composite = (1 - weight) * coverage + weight * idf_cov
            score_value = composite
        else:
            idf_cov = None
            composite = None
            score_value = overlap
        entry: Dict[str, Any] = {"doc": doc, "chunk_id": cid, "score": score_value, "text": text}
        if explanations:
            toks = matched_tokens.get((doc, cid), [])
            exp: Dict[str, Any] = {"matched_tokens": toks, "overlap": overlap, "coverage": coverage}
            if mode == "hybrid" and idf_cov is not None:
                exp.update({
                    "idf_coverage": idf_cov,
                    "embedding_weight": weight,
                    "composite": composite,
                    "scoring_mode": mode,
                })
            entry["explanation"] = exp
        scored_entries.append((score_value, entry))

    # Final ranking by (score desc, overlap desc as tiebreaker)
    scored_entries.sort(key=lambda x: x[0], reverse=True)
    for _sc, ent in scored_entries[:top_k]:
        out.append(ent)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", nargs="+", required=True, help="List of doc file paths (globs allowed)")
    ap.add_argument("--query", required=True, help="Query text")
    ap.add_argument("--top_k", type=int, default=3)
    ap.add_argument("--no_explanations", action="store_true", help="Disable explanations even if enabled in params")
    ap.add_argument("--emit_artifacts", action="store_true", help="Persist index + manifest artifacts")
    args = ap.parse_args()
    # Expand globs
    file_paths: List[pathlib.Path] = []
    for pattern in args.docs:
        expanded = glob.glob(pattern)
        if not expanded:
            file_paths.append(pathlib.Path(pattern))
        else:
            file_paths.extend(pathlib.Path(p) for p in expanded)
    files = [p for p in file_paths if p.exists() and p.is_file()]
    idx, _chunks, manifest = build_index(files)
    explanations_enabled = bool(get_runtime_param("retrieval.enable_explanations", False)) and not args.no_explanations
    results = retrieve(idx, args.query, args.top_k, explanations=explanations_enabled)
    out: Dict[str, Any] = {"query": args.query, "results": results, "count_docs": len(files), "count_chunks": len(manifest)}
    if args.emit_artifacts:
        ts = int(time.time())
        out_dir = pathlib.Path("artifacts/retrieval")
        out_dir.mkdir(parents=True, exist_ok=True)
        index_file = out_dir / f"index_{ts}.json"
        manifest_file = out_dir / f"manifest_{ts}.json"
        # Persist a simplified index: token -> list of (doc, chunk_id)
        slim_index = {tok: [(d, cid) for (d, cid, _t) in postings] for tok, postings in idx.items()}
        index_file.write_text(json.dumps(slim_index, indent=2), encoding="utf-8")
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        out["artifact_index"] = str(index_file)
        out["artifact_manifest"] = str(manifest_file)
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
