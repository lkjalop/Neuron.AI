"""Centralized feature flag & environment configuration access.

All flags follow the convention NEURON_<NAME>. Keep defaults safe & disabled.
Documented in README.
"""
from __future__ import annotations

import os
from functools import lru_cache


def _get_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=None)
def flags() -> dict:
    return {
        "SNN_ENABLED": _get_bool("NEURON_SNN_ENABLED", False),
        "REASONING_AGENT_ENABLED": _get_bool("NEURON_REASONING_AGENT_ENABLED", False),
        "RESPONSE_AUTOMATION_ENABLED": _get_bool("NEURON_RESPONSE_AUTOMATION_ENABLED", False),
        "METRICS_ENABLED": _get_bool("NEURON_METRICS_ENABLED", True),
        "DEBUG_MODE": _get_bool("NEURON_DEBUG", False),
        # Retrieval / RAG related incremental feature flags (A17)
        # Enables document corpus ingestion & query via lightweight keyword index
        "RETRIEVAL_DOCS_ENABLED": _get_bool("NEURON_RETRIEVAL_DOCS_ENABLED", False),
        # Enables inclusion of explanation fields (matched tokens, coverage, provenance hash)
        "RETRIEVAL_EXPLANATIONS_ENABLED": _get_bool("NEURON_RETRIEVAL_EXPLANATIONS_ENABLED", False),
        # Enables hashing & manifest provenance for chunks (if disabled, hashes omitted)
        "RETRIEVAL_HASH_PROVENANCE_ENABLED": _get_bool("NEURON_RETRIEVAL_HASH_PROVENANCE_ENABLED", False),
        # Feedback ingestion & enrichment (A18)
        "FEEDBACK_INGEST_ENABLED": _get_bool("NEURON_FEEDBACK_INGEST_ENABLED", False),
        "INSIGHT_CONTEXT_ENRICH_ENABLED": _get_bool("NEURON_INSIGHT_CONTEXT_ENRICH_ENABLED", False),
    }


def refresh():
    """Clear cache to pick up runtime changes (primarily for tests)."""
    flags.cache_clear()  # type: ignore[attr-defined]


__all__ = ["flags", "refresh"]
