"""In-memory retrieval corpus scaffold.

Populates entries from trace store (anomalies) with naive embeddings
(length + sum stats) to allow early similarity placeholder.
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
import os, json
from core.trace_store import traces
import math


class Corpus:
    def __init__(self):
        self._entries: List[Dict[str, Any]] = []

    def rebuild(self):
        self._entries.clear()
        for rec in traces().recent(500):
            fused = rec.get('fusion', {}) or {}
            detectors = rec.get('detectors', [])
            fired_count = sum(1 for d in detectors if d.get('fired'))
            # Derive temporal residual & confidence if temporal anomaly present
            temporal_recs = [d for d in detectors if d.get('detector') == 'temporal']
            temporal_residual = 0.0
            temporal_confidence_code = None
            temporal_mean_vec: Optional[List[float]] = None
            if temporal_recs:
                t0 = temporal_recs[0]
                temporal_residual = float(t0.get('residual_norm') or 0.0)
                temporal_confidence_code = str(t0.get('confidence_band') or '').upper() or None
                # Optionally capture normalized window mean vector if encoded
                win_mean = t0.get('mean_var')
                if isinstance(win_mean, (int, float)):
                    temporal_mean_vec = [float(win_mean)]  # placeholder until full vector stored
            vec = [float(fused.get('fused_count', 0)), float(fired_count), float(temporal_residual)]
            norm = math.sqrt(sum(v*v for v in vec)) or 1.0
            emb = [v / norm for v in vec]
            entry = {
                'event_id': rec.get('event_id'),
                'embedding': emb,
                'meta': {
                    'fused_count': fused.get('fused_count'),
                    'detectors': fired_count,
                    'temporal_residual_norm': temporal_residual,
                    'temporal_confidence_band': temporal_confidence_code,
                    'temporal_mean_vec': temporal_mean_vec,
                },
            }
            self._entries.append(entry)
        # Optional vector index upsert
        try:
            if os.getenv("NEURON_VECTOR_ENABLED", "false").lower() in {"1", "true", "yes", "on"}:
                from embeddings.base import provider  # type: ignore
                from vector.qdrant_client import upsert_vectors  # type: ignore
                texts = [json.dumps(e['meta']) for e in self._entries]
                embs = provider().embed(texts)
                # Upsert to Qdrant if client exists
                ids = [e['event_id'] or str(i) for i, e in enumerate(self._entries)]
                payloads = [e['meta'] for e in self._entries]
                upsert_vectors("neuron_corpus", ids, embs, payloads=payloads)
        except Exception:
            pass

    def query(self, query: str | None = None, top_k: int = 5, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:  # noqa: A002
        """Return top_k entries with optional metadata filter.

        filter keys supported:
          - detector: 'temporal' (future expansion)
          - confidence_band: restrict to temporal confidence band code (e.g., HIGH)
        Query string currently unused (placeholder for semantic embedding).
        """
        results = self._entries
        if filter:
            if filter.get('detector') == 'temporal':
                results = [e for e in results if e['meta'].get('temporal_residual_norm', 0.0) > 0.0]
            band = filter.get('confidence_band')
            if band:
                band_up = str(band).upper()
                results = [e for e in results if (e['meta'].get('temporal_confidence_band') or '').upper() == band_up]
        return results[:top_k]


_CORPUS: Corpus | None = None


def corpus() -> Corpus:
    global _CORPUS
    if _CORPUS is None:
        _CORPUS = Corpus()
    return _CORPUS


__all__ = ["corpus"]
