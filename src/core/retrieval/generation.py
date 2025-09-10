"""Generation provider abstraction for retrieval pipeline.

Features:
  - Runtime param gating: `retrieval.generation.enabled` (bool-like)
  - Provider selection via `retrieval.generation.provider` (values: local_hf|ollama|heuristic)
  - Model name configurable: `retrieval.generation.model` (default: google/flan-t5-small)
  - Fallback ordering: requested provider -> heuristic when failure/disabled.
  - Faithfulness proxy helpers (sentence citation coverage, unsupported entity detection).

We intentionally avoid heavy import cost unless generation is enabled.
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
import time as _time
import os, time, json, math, re

try:
    from config import runtime_params  # type: ignore
except Exception:  # pragma: no cover
    runtime_params = None  # type: ignore

_HF_MODEL = None
_HF_TOKENIZER = None
_HF_MODEL_NAME = None
_OLLAMA_AVAILABLE = False  # lazily probed

def _rp(name: str, default: Any) -> Any:  # type: ignore[override]
    try:
        if runtime_params is None:
            return default
        v = runtime_params.get_param(name)
        return v if v is not None else default
    except Exception:
        return default


def _generation_enabled() -> bool:
    # Disabled by default to avoid heavy model load unless explicitly enabled
    v = _rp("retrieval.generation.enabled", 0)
    return v in {1, "1", True, "true", "yes", "on"}


def _provider() -> str:
    return str(_rp("retrieval.generation.provider", "local_hf") or "local_hf")


def _model_name() -> str:
    return str(_rp("retrieval.generation.model", "google/flan-t5-small") or "google/flan-t5-small")


def _lazy_load_hf() -> bool:
    global _HF_MODEL, _HF_TOKENIZER, _HF_MODEL_NAME
    if _HF_MODEL is not None:
        return True
    try:
        import transformers  # type: ignore
        model_name = _model_name()
        t0 = _time.time()
        _HF_TOKENIZER = transformers.AutoTokenizer.from_pretrained(model_name)
        _HF_MODEL = transformers.AutoModelForSeq2SeqLM.from_pretrained(model_name)
        _HF_MODEL_NAME = model_name
        # Optional: record load latency metric when metrics module extended later
        return True
    except Exception:
        _HF_MODEL = None
        return False


def _ollama_generate(prompt: str, model: str) -> Optional[str]:
    """Query local Ollama server (best-effort)."""
    import json, urllib.request
    try:
        data = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request("http://localhost:11434/api/generate", data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as resp:  # nosec
            raw = resp.read().decode()
        obj = json.loads(raw)
        return obj.get("response") or obj.get("data") or raw
    except Exception:
        return None


def _build_context_prompt(contexts: List[Dict[str, Any]], query: str, max_ctx_tokens: int = 512) -> str:
    parts: List[str] = ["You are a security retrieval assistant. Answer the user query using ONLY the provided chunks. Cite provenance ids in parentheses ()."]
    total = 0
    for i, c in enumerate(contexts):
        exp = c.get("explanation") or {}
        toks = exp.get("matched_tokens") or []
        prov = exp.get("provenance_hash") or f"{c.get('doc')}#{c.get('chunk_id')}"
        snippet = " ".join(toks[:40])
        token_len = len(snippet.split())
        if total + token_len > max_ctx_tokens:
            break
        parts.append(f"[CTX {i} id={prov}] {snippet}")
        total += token_len
    parts.append(f"Query: {query}\nAnswer concisely:")
    return "\n".join(parts)


def _heuristic_answer(contexts: List[Dict[str, Any]], query: str, max_tokens: int) -> str:
    tokens: list[str] = []
    for c in contexts:
        exp = c.get("explanation") or {}
        for t in (exp.get("matched_tokens") or []):
            if t not in tokens:
                tokens.append(t)
            if len(tokens) >= max_tokens:
                break
        if len(tokens) >= max_tokens:
            break
    if not tokens:
        return "No relevant context retrieved for query." if contexts else "No context available."
    return "Answer (heuristic): " + " ".join(tokens[:max_tokens])


def generate_answer(contexts: List[Dict[str, Any]], query: str, max_tokens: int = 120, provider: Optional[str] = None) -> str:
    """Generate an answer using selected provider or fallback heuristic."""
    if not _generation_enabled():
        return _heuristic_answer(contexts, query, max_tokens)
    prov = provider or _provider()
    # Heuristic fast path when no contexts
    if not contexts:
        return _heuristic_answer(contexts, query, max_tokens)
    prompt = _build_context_prompt(contexts, query)
    full_t0 = _time.time()
    if prov == "local_hf":
        if _lazy_load_hf():
            try:
                assert _HF_MODEL is not None and _HF_TOKENIZER is not None  # for type checkers
                import torch  # type: ignore
                inputs = _HF_TOKENIZER(prompt, return_tensors="pt", truncation=True, max_length=768)
                # Approx first-token latency: encode + first forward (forced one token)
                first_token_latency = None
                try:
                    first_t0 = _time.time()
                    with torch.inference_mode():  # type: ignore[attr-defined]
                        outputs_ft = _HF_MODEL.generate(**inputs, max_new_tokens=1, do_sample=False)
                    first_token_latency = _time.time() - first_t0
                    # Continue generation for remaining tokens (subtract 1 already generated)
                    remaining = max(0, max_tokens - 1)
                    if remaining > 0:
                        with torch.inference_mode():
                            outputs_rem = _HF_MODEL.generate(**inputs, max_new_tokens=max_tokens, do_sample=False)
                        # use longer output
                        outputs = outputs_rem
                    else:
                        outputs = outputs_ft
                except Exception:
                    # Fallback: single pass generation
                    with torch.inference_mode():
                        outputs = _HF_MODEL.generate(**inputs, max_new_tokens=max_tokens, do_sample=False)
                text = _HF_TOKENIZER.decode(outputs[0], skip_special_tokens=True)
                full_latency = _time.time() - full_t0
                try:
                    from core.metrics import (
                        RETRIEVAL_GENERATION_FIRST_TOKEN_LATENCY,
                        RETRIEVAL_GENERATION_FULL_LATENCY,
                    )  # type: ignore
                    if first_token_latency is not None:
                        RETRIEVAL_GENERATION_FIRST_TOKEN_LATENCY.observe(first_token_latency)  # type: ignore[attr-defined]
                    RETRIEVAL_GENERATION_FULL_LATENCY.observe(full_latency)  # type: ignore[attr-defined]
                except Exception:
                    pass
                return text.strip()
            except Exception:
                return _heuristic_answer(contexts, query, max_tokens)
        else:
            return _heuristic_answer(contexts, query, max_tokens)
    elif prov == "ollama":
        model = _model_name()  # user can supply local model id (e.g., mistral, llama2)
        out = _ollama_generate(prompt, model)
        if out:
            return out.strip()
        return _heuristic_answer(contexts, query, max_tokens)
    else:  # explicit heuristic
        return _heuristic_answer(contexts, query, max_tokens)


# --- Faithfulness Proxies -------------------------------------------------
def sentence_citation_coverage(answer: str, citations: List[Dict[str, Any]]) -> float:
    """Compute fraction of sentences that include at least one provenance id token.

    We look for provenance IDs (provenance hash) appearing in sentence text.
    """
    try:
        import re
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if s.strip()]
        if not sentences:
            return 0.0
        provs = set()
        for c in citations:
            p = c.get("provenance")
            if p:
                provs.add(str(p))
        if not provs:
            return 0.0
        covered = 0
        for s in sentences:
            s_l = s.lower()
            if any(p.lower() in s_l for p in provs):
                covered += 1
        return covered / max(1, len(sentences))
    except Exception:
        return 0.0


def unsupported_entities(answer: str, contexts: List[Dict[str, Any]]) -> Tuple[int, List[str]]:
    """Detect entities (simple CVE IDs & numbers) not present in matched tokens."""
    try:
        import re
        grounded = set()
        for c in contexts:
            exp = c.get("explanation") or {}
            for t in (exp.get("matched_tokens") or []):
                grounded.add(str(t).lower())
        entities: List[str] = []
        cve_pattern = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)
        num_pattern = re.compile(r"\b\d+\b")
        for cve in cve_pattern.findall(answer):
            if cve.lower() not in grounded:
                entities.append(cve)
        for num in num_pattern.findall(answer):
            if num.lower() not in grounded:
                entities.append(num)
        return len(entities), entities
    except Exception:
        return 0, []

def warmup_generation(model: str | None = None) -> dict:
    """Warm up generation provider (currently HF local seq2seq only).

    Loads model/tokenizer into memory if not already loaded and performs a
    lightweight single forward pass with a trivial prompt. Returns timing info.
    Safe no-op if provider disabled or transformers unavailable.
    """
    provider = _rp("retrieval.generation.provider", "hf_local")
    enabled = _rp("retrieval.generation.enabled", 0)
    if not enabled:
        return {"status": "disabled"}
    if provider != "hf_local":
        return {"status": "skipped", "reason": "provider_not_hf_local"}
    model_name = model or _rp("retrieval.generation.model", "google/flan-t5-small")
    t0 = time.time()
    try:
        m, tok = _lazy_load_hf(model_name)
        # Single token generation warmup (no gradients)
        if m and tok:
            import torch  # type: ignore
            with torch.inference_mode():  # type: ignore[attr-defined]
                inp = tok("Warmup.", return_tensors="pt")
                _ = m.generate(**inp, max_new_tokens=2)
        dt = time.time() - t0
        try:
            from core.metrics import RETRIEVAL_GENERATION_WARMUP_LATENCY  # type: ignore
            RETRIEVAL_GENERATION_WARMUP_LATENCY.observe(dt)  # type: ignore[attr-defined]
        except Exception:
            pass
        return {"status": "ok", "latency_s": round(dt, 4), "model": model_name}
    except Exception as e:  # pragma: no cover
        return {"status": "error", "error": str(e)}

__all__ = [
    "generate_answer",
    "sentence_citation_coverage",
    "unsupported_entities",
    "warmup_generation",
]
