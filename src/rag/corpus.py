"""RAG Corpus Builder (skeleton).

Maintains a lightweight in-memory corpus of documents for retrieval-augmented
reasoning. Designed for later replacement by a vector index or hybrid search.

Features:
  - add_document(id, text, metadata)
  - get_document(id)
  - list_documents(limit)
  - search(query, top_k): keyword scoring + optional hybrid weight

Scoring:
  * Keyword score = sum( term_freq(term, doc) ) over unique query terms
  * Optional embedding similarity stub: stable hash overlap ratio (simulated)
  * Final score = (1 - w) * keyword + w * embedding where w = retrieval.hybrid.embedding_weight

Runtime Params Used:
  retrieval.scoring.mode : keyword | hybrid
  retrieval.hybrid.embedding_weight : (0..1)

NOTE: All operations are in-memory; persistence and incremental indexing left
for future enhancement.
"""
from __future__ import annotations

from typing import Dict, Any, List, Tuple
import re, hashlib, json, math, os
from pathlib import Path
from config.runtime_params import get_param  # type: ignore
try:
    from rag.embeddings import get_provider as _get_embed_provider  # type: ignore
except Exception:  # pragma: no cover
    _get_embed_provider = None  # type: ignore

_CORPUS: Dict[str, Dict[str, Any]] = {}
_BASE_DIR = Path("artifacts/rag")
_PERSIST_FILE = _BASE_DIR / "rag_corpus.json"
_ARTIFACT_VERSION = 1  # bump when on-disk format changes

WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in WORD_RE.findall(text)]


def _doc_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tenant_path(tenant: str | None) -> Path:
    if tenant and (os.getenv("RETRIEVAL_TENANT_PARTITION", "0") in {"1","true","TRUE"}):
        return _BASE_DIR / tenant / "rag_corpus.json"
    return _PERSIST_FILE


def add_document(doc_id: str, text: str, metadata: Dict[str, Any] | None = None, embedding: List[float] | None = None, tenant: str | None = None) -> Dict[str, Any]:
    tokens = _tokenize(text)
    rec = {
        "id": doc_id,
        "text": text,
        "tokens": tokens,
        "metadata": metadata or {},
        "hash": _doc_hash(text),
    }
    if embedding is not None:
        rec["embedding"] = list(embedding)
    _CORPUS[doc_id] = rec
    return rec


def get_document(doc_id: str) -> Dict[str, Any] | None:
    return _CORPUS.get(doc_id)


def list_documents(limit: int = 100) -> List[Dict[str, Any]]:
    return list(_CORPUS.values())[:limit]


def save(tenant: str | None = None) -> int:
    """Persist corpus documents with artifact version wrapper.

    Format (v1): {"version": 1, "documents": [ {id,text,metadata}... ]}
    Legacy list format still accepted on load.
    """
    try:
        path = _tenant_path(tenant)
        path.parent.mkdir(parents=True, exist_ok=True)
        docs = [
            {k: v for k, v in rec.items() if k in {"id", "text", "metadata", "hash"}}
            for rec in _CORPUS.values()
        ]
        payload = {"version": _ARTIFACT_VERSION, "documents": docs}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return len(docs)
    except Exception:
        return 0


def load(tenant: str | None = None) -> int:
    path = _tenant_path(tenant)
    if not path.exists():
        return 0
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        docs = []
        if isinstance(data, dict) and "documents" in data:
            docs = data.get("documents") or []
        elif isinstance(data, list):  # legacy
            docs = data
        if isinstance(docs, list):
            _CORPUS.clear()
            for rec in docs:
                if isinstance(rec, dict) and rec.get("id") and rec.get("text"):
                    add_document(rec["id"], rec["text"], rec.get("metadata"), tenant=tenant)
            return len(_CORPUS)
    except Exception:
        return 0
    return 0


def _embedding_hash_vector(tokens: List[str]) -> set[str]:
    # Simulated embedding: set of first 8 hex chars of sha256 per token
    out = set()
    for t in tokens[:128]:  # cap cost
        h = hashlib.sha256(t.encode("utf-8")).hexdigest()[:8]
        out.add(h)
    return out


def _hybrid_similarity(q_tokens: List[str], doc_tokens: List[str]) -> float:
    qv = _embedding_hash_vector(q_tokens)
    dv = _embedding_hash_vector(doc_tokens)
    if not dv:
        return 0.0
    inter = len(qv & dv)
    return inter / max(1, len(qv | dv))


# ---------------- Vector (pseudo) embedding support -----------------
_EMBED_DIM = 32  # small fixed dim for deterministic pseudo-embeddings


def _text_embedding(tokens: List[str]) -> List[float]:
    # Prefer external embedding provider if registered (provider returns normalized vector)
    if _get_embed_provider:
        try:
            provider = _get_embed_provider()
            return provider(" ".join(tokens))
        except Exception:
            pass
    # Fallback deterministic hash embedding
    vec = [0.0] * _EMBED_DIM
    if not tokens:
        return vec
    for t in tokens[:256]:
        h = int(hashlib.sha256(t.encode("utf-8")).hexdigest()[:8], 16)
        vec[h % _EMBED_DIM] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    if dot <= 0:
        return 0.0
    # vectors already normalized when produced by _text_embedding
    return min(1.0, max(0.0, dot))


def set_embedding(doc_id: str, embedding: List[float]) -> bool:
    rec = _CORPUS.get(doc_id)
    if not rec:
        return False
    rec["embedding"] = list(embedding)
    return True


def search(query: str, top_k: int = 5) -> List[Tuple[str, float]]:
    if top_k <= 0:
        return []
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []
    mode = (get_param("retrieval.scoring.mode") or "keyword").lower()
    hybrid_w = float(get_param("retrieval.hybrid.embedding_weight") or 0.3)
    unique_q = set(q_tokens)
    scores: List[Tuple[str, float]] = []
    # Precompute query vector if vector modes requested
    q_vec: List[float] | None = None
    if mode in {"vector", "hybrid_vector"}:
        q_vec = _text_embedding(q_tokens)
    for doc_id, rec in _CORPUS.items():
        tks = rec["tokens"]
        # Keyword component (shared across modes)
        tf = sum(tks.count(term) for term in unique_q)
        kw_score = tf / max(1, len(tks))
        score = kw_score
        if mode == "hybrid":
            emb = _hybrid_similarity(q_tokens, tks)
            score = (1 - hybrid_w) * kw_score + hybrid_w * emb
        elif mode == "vector":
            if q_vec is not None:
                d_vec = rec.get("embedding")
                if d_vec is None:
                    d_vec = _text_embedding(tks)
                    rec["embedding"] = d_vec  # cache
                score = _cosine(q_vec, d_vec)
        elif mode == "hybrid_vector":
            if q_vec is not None:
                d_vec = rec.get("embedding")
                if d_vec is None:
                    d_vec = _text_embedding(tks)
                    rec["embedding"] = d_vec
                v_sim = _cosine(q_vec, d_vec)
                score = (1 - hybrid_w) * kw_score + hybrid_w * v_sim
        if score > 0:
            scores.append((doc_id, float(score)))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


__all__ = [
    "add_document",
    "get_document",
    "list_documents",
    "search",
    "save",
    "load",
    "set_embedding",
    "_ARTIFACT_VERSION",
]
