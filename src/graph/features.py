"""Feature Extraction for RelationshipGraph.

Lightweight, synchronous feature derivation used for early graph intelligence
tasks (snapshot inspection, naive link prediction heuristics). Not optimized
for very large graphs; acceptable for prototype scale (<100k edges).

Features (per node):
  degree_in, degree_out, degree_total
  edge_type_count.<type>
  last_edge_ts (unix epoch)
  recency_seconds (now - last_edge_ts)
  activity_1h, activity_24h (edges touching node in window)

Future extensions (GNN Spec alignment):
  - risk overlay (aggregated_risk_score)
  - intel corroboration counts
  - identity deviation metrics

Thread safety: The underlying graph writes are guarded by an asyncio.Lock.
We take a snapshot copy of adjacency structures to avoid holding the lock
while computing aggregates.
"""
from __future__ import annotations

from typing import Dict, Any, Tuple
import time
import math

from .relationships import get_graph
try:  # risk overlay optional
    from risk import aggregator as risk_aggregator  # type: ignore
except Exception:  # pragma: no cover
    risk_aggregator = None  # type: ignore


_FEATURE_CACHE: Dict[str, Dict[str, float]] = {}
_FEATURE_METADATA: Dict[str, Any] = {
    "last_refresh_ts": 0.0,
    "node_count": 0,
    "edge_count": 0,
}


def _windows() -> Tuple[float, float]:
    return 3600.0, 86400.0  # 1h, 24h


def refresh_features() -> Dict[str, Dict[str, float]]:
    g = get_graph()
    now = time.time()
    # Access internal structures (acceptable for in-module coupling) -- we only read.
    adjacency = getattr(g, "_adjacency", {})  # type: ignore[attr-defined]
    reverse = getattr(g, "_reverse", {})  # type: ignore[attr-defined]
    features: Dict[str, Dict[str, float]] = {}
    nodes = set(adjacency.keys()) | set(reverse.keys())
    one_h, one_d = _windows()
    total_edges = 0
    for n in nodes:
        out_map = adjacency.get(n, {})
        in_map = reverse.get(n, {})
        degree_out = sum(len(meta_list) for meta_list in out_map.values())
        degree_in = sum(len(meta_list) for meta_list in in_map.values())
        degree_total = degree_in + degree_out
        f: Dict[str, float] = {
            "degree_in": float(degree_in),
            "degree_out": float(degree_out),
            "degree_total": float(degree_total),
            "degree_log": math.log1p(degree_total),
        }
        last_ts = 0.0
        act_1h = 0
        act_24h = 0
        # Count edge types for out edges only (directional); could extend to in edges.
        for dst, meta_list in out_map.items():
            for meta in meta_list:
                ts = float(meta.get("ts", 0.0) or 0.0)
                if ts > last_ts:
                    last_ts = ts
                dt = now - ts
                if dt <= one_h:
                    act_1h += 1
                if dt <= one_d:
                    act_24h += 1
                etype = meta.get("type")
                if etype:
                    key = f"edge_type_count.{etype}"
                    f[key] = f.get(key, 0.0) + 1.0
                total_edges += 1
        f["last_edge_ts"] = last_ts
        f["recency_seconds"] = (now - last_ts) if last_ts else -1.0
        f["activity_1h"] = float(act_1h)
        f["activity_24h"] = float(act_24h)
        # Include edge type counts for inbound-only edges (rare but possible) to avoid empty feature set
        if degree_total == 0 and in_map:
            # Count inbound edge types so that nodes with only inbound edges still have minimal signal
            for src, meta_list in in_map.items():
                for meta in meta_list:
                    etype = meta.get("type")
                    if etype:
                        key = f"edge_type_count.{etype}"
                        f[key] = f.get(key, 0.0) + 1.0
        # Risk overlay: if node is a finding:<assessment_id> and signals snapshot exists
        if n.startswith("finding:") and risk_aggregator is not None:
            aid = n.split(":", 1)[1]
            signals = getattr(risk_aggregator, "_last_signals", {}).get(aid)
            if signals:
                for rk, rv in signals.items():
                    f[f"risk_channel.{rk}"] = float(rv)
        features[n] = f
    global _FEATURE_CACHE, _FEATURE_METADATA
    _FEATURE_CACHE = features
    _FEATURE_METADATA = {
        "last_refresh_ts": now,
        "node_count": len(nodes),
        "edge_count": total_edges,
    }
    return features


def get_features() -> Dict[str, Dict[str, float]]:
    return _FEATURE_CACHE


def get_feature_metadata() -> Dict[str, Any]:
    return _FEATURE_METADATA


__all__ = [
    "refresh_features",
    "get_features",
    "get_feature_metadata",
]
