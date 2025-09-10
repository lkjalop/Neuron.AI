"""Context window optimizer (Batch 20).

Greedy token coverage selection with simple redundancy penalty.

Inputs:
  candidates: list of dicts each having at least keys:
      - key: tuple(doc, chunk_id) unique identifier
      - tokens: list[str] matched (normalized) tokens for this chunk
      - score: original retrieval score (float) used for tie-breaking
  token_budget: maximum number of unique tokens to cover (approximation of model window budget)
  redundancy_penalty: float in [0,1] decreasing marginal gain for already covered tokens.

Algorithm:
  Repeatedly choose candidate with highest effective_gain where
      effective_gain = new_token_count - redundancy_penalty * overlapping_count
  Stop when no positive gain or budget exhausted.

Returns (selected_keys, coverage_ratio, covered_tokens_set)
  coverage_ratio = len(covered_tokens) / len(all_tokens)

This is intentionally lightweight and deterministic (stable ordering by score then doc id) to
facilitate deterministic replay testing.
"""
from __future__ import annotations
from typing import List, Dict, Tuple, Set


def optimize_window(
    candidates: List[Dict],
    token_budget: int | None = None,
    redundancy_penalty: float = 0.15,
) -> Tuple[Set[Tuple[str,int]], float, Set[str]]:
    if not candidates:
        return set(), 0.0, set()
    all_tokens: Set[str] = set()
    for c in candidates:
        for t in c.get("tokens", []):
            all_tokens.add(t)
    if not all_tokens:
        # Nothing to optimize
        return set((c.get("key") for c in candidates if c.get("key"))), 1.0, set()
    if token_budget is None or token_budget <= 0:
        token_budget = len(all_tokens)
    redundancy_penalty = max(0.0, min(1.0, redundancy_penalty))
    covered: Set[str] = set()
    selected: Set[Tuple[str,int]] = set()
    remaining = list(candidates)
    # Deterministic ordering baseline
    remaining.sort(key=lambda c: (-(c.get("score") or 0.0), c.get("key")))
    while remaining and len(covered) < token_budget:
        best = None
        best_gain = 0.0
        best_new_tokens: Set[str] | None = None
        for c in remaining:
            toks = set(c.get("tokens", []))
            new = toks - covered
            if not new:
                continue
            overlap = len(toks & covered)
            gain = len(new) - redundancy_penalty * overlap
            if gain > best_gain + 1e-9:  # numeric stability
                best = c
                best_gain = gain
                best_new_tokens = new
        if best is None or best_gain <= 0:
            break
        selected.add(best.get("key"))  # type: ignore[arg-type]
        covered.update(best_new_tokens)  # type: ignore[arg-type]
        remaining = [c for c in remaining if c is not best]
    coverage_ratio = len(covered) / max(1, len(all_tokens))
    return selected, coverage_ratio, covered

__all__ = ["optimize_window"]
