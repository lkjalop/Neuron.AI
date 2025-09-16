"""Graph-Lite Relationship Store

Lightweight in-memory relationship graph to support early contextual
correlation without pulling in a full graph database dependency.

Use Cases (initial):
  - Link findings to assets, identities, processes, domains
  - Simple traversal to answer: "what else is connected?"
  - Path existence queries for lateral movement suspicion

Design Principles:
  - Pure in-memory; restart wipes state (acceptable for prototype)
  - Thread-safe via coarse asyncio.Lock (writes) to enable async usage
  - Directional edges with optional type & weight metadata
  - Compact export for future persistence / visualization

Future Extensions:
  - TTL / decay for stale relationships
  - Attribute indexing (e.g., by relationship type)
  - Centrality / community heuristics
  - Optional persistence adapter (Redis / SQLite / Neo4j)
"""
from __future__ import annotations

from typing import Dict, List, Tuple, Optional, Iterable, Set, Any
import asyncio
import time


NEW_EDGE_TYPES = {
    # domain -> asset (e.g., domain resolves to asset / host)
    "resolves_to",
    # identity -> asset (user/session authenticates to host/asset)
    "authenticates_to",
    # identity -> finding (user implicated in generating a finding / alert)
    "implicated_in",
    # ioc -> finding (indicator observed within a finding context)
    "indicator_of",
}


class RelationshipGraph:
    def __init__(self):
        # adjacency[src][dst] = list[edge_metadata]
        self._adjacency: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        # reverse adjacency for faster inbound queries
        self._reverse: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        self._lock = asyncio.Lock()

    async def add_edge(
        self,
        src: str,
        dst: str,
        rel_type: str = "related",
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        bidirectional: bool = False,
    ) -> None:
        """Add a relationship edge.

        Parameters:
          src/dst: node identifiers (arbitrary strings)
          rel_type: semantic label (e.g., "owns", "resolves_to", "parent_process")
          weight: simple scoring weight (0..inf, not normalized here)
          metadata: optional arbitrary details (timestamps, evidence id)
          bidirectional: when True, also creates the reverse edge with same meta
        """
        if not src or not dst:
            return
        edge_meta = {
            "type": rel_type,
            "weight": weight,
            "ts": time.time(),
        }
        if metadata:
            edge_meta.update(metadata)
        async with self._lock:
            self._adjacency.setdefault(src, {}).setdefault(dst, []).append(edge_meta)
            self._reverse.setdefault(dst, {}).setdefault(src, []).append(edge_meta)
            if bidirectional:
                # Mirror edge (independent metadata instance)
                rev_meta = edge_meta.copy()
                self._adjacency.setdefault(dst, {}).setdefault(src, []).append(rev_meta)
                self._reverse.setdefault(src, {}).setdefault(dst, []).append(rev_meta)

    # Convenience semantic helpers -------------------------------------------------

    async def link_domain_asset(self, domain: str, asset: str, **metadata: Any) -> None:
        """Record that a domain resolves to (is associated with) an asset.

        domain: raw domain or FQDN (will be normalized to lowercase)
        asset: internal asset identifier/hostname
        """
        if not domain or not asset:
            return
        await self.add_edge(f"domain:{domain.lower()}", f"asset:{asset}", rel_type="resolves_to", metadata=metadata)

    async def link_identity_asset(self, identity: str, asset: str, auth_method: str | None = None, **metadata: Any) -> None:
        """Record an authentication / session from identity to asset."""
        if not identity or not asset:
            return
        meta = dict(metadata)
        if auth_method:
            meta["auth_method"] = auth_method
        await self.add_edge(f"identity:{identity}", f"asset:{asset}", rel_type="authenticates_to", metadata=meta)

    async def link_identity_finding(self, identity: str, finding_id: str, role: str | None = None, **metadata: Any) -> None:
        """Associate an identity as implicated in a finding / alert."""
        if not identity or not finding_id:
            return
        meta = dict(metadata)
        if role:
            meta["role"] = role
        await self.add_edge(f"identity:{identity}", f"finding:{finding_id}", rel_type="implicated_in", metadata=meta)

    async def link_ioc_finding(self, ioc: str, finding_id: str, ioc_type: str | None = None, **metadata: Any) -> None:
        """Associate an indicator of compromise with a finding (indicator observed within finding context)."""
        if not ioc or not finding_id:
            return
        meta = dict(metadata)
        if ioc_type:
            meta["ioc_type"] = ioc_type
        await self.add_edge(f"ioc:{ioc}", f"finding:{finding_id}", rel_type="indicator_of", metadata=meta)

    def neighbors(self, node: str, rel_type: Optional[str] = None) -> List[str]:
        edges = self._adjacency.get(node, {})
        out = []
        for dst, meta_list in edges.items():
            if rel_type is None or any(m.get("type") == rel_type for m in meta_list):
                out.append(dst)
        return out

    def nodes(self) -> List[str]:
        """Return list of node identifiers currently present in the graph."""
        return sorted(set(self._adjacency.keys()) | set(self._reverse.keys()))

    def outgoing_edges(self, node: str) -> List[Dict[str, Any]]:
        """Return all outgoing edges (expanded) for a node: list of {src,dst,type,weight,ts}."""
        out: List[Dict[str, Any]] = []
        for dst, metas in self._adjacency.get(node, {}).items():
            for m in metas:
                rec = {"src": node, "dst": dst, **m}
                out.append(rec)
        return out

    def incoming_edges(self, node: str) -> List[Dict[str, Any]]:
        """Return all incoming edges for a node in same structure as outgoing_edges."""
        inc: List[Dict[str, Any]] = []
        for src, metas in self._reverse.get(node, {}).items():
            for m in metas:
                rec = {"src": src, "dst": node, **m}
                inc.append(rec)
        return inc

    def inbound(self, node: str, rel_type: Optional[str] = None) -> List[str]:
        edges = self._reverse.get(node, {})
        out = []
        for src, meta_list in edges.items():
            if rel_type is None or any(m.get("type") == rel_type for m in meta_list):
                out.append(src)
        return out

    def path_exists(self, start: str, target: str, max_depth: int = 4) -> bool:
        if start == target:
            return True
        if max_depth <= 0:
            return False
        visited: Set[str] = {start}
        frontier: List[Tuple[str, int]] = [(start, 0)]
        while frontier:
            node, depth = frontier.pop()
            if depth >= max_depth:
                continue
            for nxt in self._adjacency.get(node, {}):
                if nxt == target:
                    return True
                if nxt not in visited:
                    visited.add(nxt)
                    frontier.append((nxt, depth + 1))
        return False

    def find_related(self, node: str, depth: int = 2) -> List[str]:
        related: Set[str] = set()
        frontier: List[Tuple[str, int]] = [(node, 0)]
        visited: Set[str] = {node}
        while frontier:
            cur, d = frontier.pop()
            if d >= depth:
                continue
            for nxt in self._adjacency.get(cur, {}):
                if nxt not in visited:
                    visited.add(nxt)
                    related.add(nxt)
                    frontier.append((nxt, d + 1))
        return sorted(related)

    def export(self) -> Dict[str, Any]:
        nodes = set(self._adjacency.keys()) | set(self._reverse.keys())
        edges = []
        type_counts: Dict[str, int] = {}
        for src, dst_map in self._adjacency.items():
            for dst, meta_list in dst_map.items():
                for meta in meta_list:
                    etype = meta.get("type")
                    if etype:
                        type_counts[etype] = type_counts.get(etype, 0) + 1
                    edges.append({"src": src, "dst": dst, **meta})
        return {"nodes": sorted(nodes), "edges": edges, "edge_type_counts": type_counts}

    async def prune_stale(self, max_age_seconds: float, node_prefixes: Optional[List[str]] = None) -> int:
        """Prune edges (and orphaned nodes) whose latest timestamp is older than max_age_seconds.

        node_prefixes: optional list of node id prefixes to restrict pruning scope (e.g., ["ioc:", "finding:"]).
        Returns number of edges removed.
        """
        cutoff = time.time() - max_age_seconds
        removed = 0
        async with self._lock:
            to_delete_src: List[Tuple[str, str, Dict[str, Any]]] = []
            for src, dst_map in self._adjacency.items():
                if node_prefixes and not any(src.startswith(p) for p in node_prefixes):
                    continue
                for dst, meta_list in list(dst_map.items()):
                    # Filter meta_list in place
                    keep = []
                    for meta in meta_list:
                        if meta.get("ts", 0) < cutoff:
                            removed += 1
                        else:
                            keep.append(meta)
                    if keep:
                        dst_map[dst] = keep
                    else:
                        del dst_map[dst]
            # Rebuild reverse map (simpler than selective cleanup) after pruning
            self._reverse = {}
            for s, dst_map in self._adjacency.items():
                for d, metas in dst_map.items():
                    for m in metas:
                        self._reverse.setdefault(d, {}).setdefault(s, []).append(m)
        return removed


_singleton: Optional[RelationshipGraph] = None


def get_graph() -> RelationshipGraph:
    global _singleton
    if _singleton is None:
        _singleton = RelationshipGraph()
    return _singleton

# --- Module Alias Bridging ---------------------------------------------------
# Tests import get_graph via 'src.graph.relationships' while application routers
# import 'graph.relationships' (after adding 'src' to sys.path). This results in
# two separate module objects with independent `_singleton` variables, causing
# seeded edges to be invisible to API endpoints (features/embeddings see an
# empty graph). We reconcile by ensuring both module namespaces reference the
# same singleton instance whenever this file is imported under either name.
import sys as _sys  # noqa: E402
try:  # best-effort; silent on failure
    _src_mod = _sys.modules.get('src.graph.relationships')
    _plain_mod = _sys.modules.get('graph.relationships')
    if _src_mod and _plain_mod:
        # Prefer an existing populated singleton if one side already created it
        src_singleton = getattr(_src_mod, '_singleton', None)
        plain_singleton = getattr(_plain_mod, '_singleton', None)
        chosen = src_singleton or plain_singleton
        if chosen:
            # Propagate to both
            try:
                if getattr(_src_mod, '_singleton', None) is not chosen:
                    setattr(_src_mod, '_singleton', chosen)
            except Exception:
                pass
            try:
                if getattr(_plain_mod, '_singleton', None) is not chosen:
                    setattr(_plain_mod, '_singleton', chosen)
            except Exception:
                pass
            # Also update local name if different
            if '_singleton' in globals() and globals().get('_singleton') is not chosen:
                _singleton = chosen  # type: ignore[assignment]
except Exception:
    pass


__all__ = [
    "RelationshipGraph",
    "get_graph",
    "NEW_EDGE_TYPES",
]
