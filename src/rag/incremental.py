"""Incremental corpus ingestion utilities (Batch 20)."""
from __future__ import annotations
from typing import List, Dict, Any
import hashlib

from . import corpus


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def diff_ingest(docs: List[Dict[str, Any]], tenant: str | None = None) -> Dict[str, Any]:
    """Ingest documents incrementally.

    Each doc requires keys: id, text, (optional metadata).
    Returns: {added: int, updated: int, unchanged: int}
    """
    added = updated = unchanged = 0
    # Build index of existing
    existing = {d['id']: d for d in corpus.list_documents(10_000)}
    for d in docs:
        if not isinstance(d, dict):
            continue
        did = d.get('id')
        txt = d.get('text')
        if not did or not isinstance(txt, str):
            continue
        new_hash = _hash(txt)
        cur = existing.get(did)
        if cur:
            if cur.get('hash') == new_hash:
                unchanged += 1
                continue
            # update
            corpus.add_document(did, txt, d.get('metadata'), tenant=tenant)
            updated += 1
        else:
            corpus.add_document(did, txt, d.get('metadata'), tenant=tenant)
            added += 1
    corpus.save(tenant=tenant)
    return {"added": added, "updated": updated, "unchanged": unchanged}

__all__ = ["diff_ingest"]
