"""Graph persistence abstraction (relational-backed) for knowledge + vulnerability domain.

Tables expected (DDL reference - create via migration tooling or manual):

  CREATE TABLE graph_nodes (
      id TEXT PRIMARY KEY,
      node_type TEXT NOT NULL,
      properties JSONB NOT NULL DEFAULT '{}',
      created_ts DOUBLE PRECISION NOT NULL,
      updated_ts DOUBLE PRECISION NOT NULL
  );
  CREATE INDEX ON graph_nodes(node_type);

  CREATE TABLE graph_edges (
      src_id TEXT NOT NULL,
      dst_id TEXT NOT NULL,
      edge_type TEXT NOT NULL,
      properties JSONB NOT NULL DEFAULT '{}',
      created_ts DOUBLE PRECISION NOT NULL,
      PRIMARY KEY (src_id, dst_id, edge_type),
      FOREIGN KEY (src_id) REFERENCES graph_nodes(id) ON DELETE CASCADE,
      FOREIGN KEY (dst_id) REFERENCES graph_nodes(id) ON DELETE CASCADE
  );
  CREATE INDEX ON graph_edges(edge_type);
  CREATE INDEX ON graph_edges(dst_id);

Node Type Conventions (initial):
  - VULNERABILITY (cve id or vendor id)
  - ASSET
  - KNOWLEDGE_ARTICLE (SOC FAQ / How-To)
  - PROCEDURE (operational playbook steps)
  - CONTROL (framework control: e.g., CIS-1.1, NIST-CSF-PR.AC-1)
  - ATTACK_PATTERN (MITRE ATT&CK technique or CAPEC)
  - REMEDIATION_TASK

Edge Type Conventions (initial):
  - EXPLOITS (ATTACK_PATTERN -> VULNERABILITY)
  - AFFECTS (VULNERABILITY -> ASSET)
  - MITIGATES (CONTROL -> VULNERABILITY)
  - IMPLEMENTS (PROCEDURE -> CONTROL)
  - RELATES_TO (generic article relation: KNOWLEDGE_ARTICLE -> *)
  - REMEDIATES (REMEDIATION_TASK -> VULNERABILITY)

Future: move to specialized graph backend or add vector adjacency caches.
"""
from __future__ import annotations

from typing import Any, Dict, List, Iterable, Optional
import time
import json

from . import postgres


STANDARD_NODE_TYPES = {
    "VULNERABILITY",
    "ASSET",
    "KNOWLEDGE_ARTICLE",
    "PROCEDURE",
    "CONTROL",
    "ATTACK_PATTERN",
    "REMEDIATION_TASK",
}

STANDARD_EDGE_TYPES = {
    "EXPLOITS",
    "AFFECTS",
    "MITIGATES",
    "IMPLEMENTS",
    "RELATES_TO",
    "REMEDIATES",
}


async def upsert_node(node_id: str, node_type: str, properties: Dict[str, Any] | None = None) -> None:
    if node_type not in STANDARD_NODE_TYPES:
        # Allow extension but tag unknown for later audit
        pass
    now = float(time.time())
    props = json.dumps(properties or {})
    await postgres.execute(
        """
        INSERT INTO graph_nodes (id, node_type, properties, created_ts, updated_ts)
        VALUES ($1,$2,$3,$4,$4)
        ON CONFLICT (id) DO UPDATE SET
          node_type=EXCLUDED.node_type,
          properties=EXCLUDED.properties,
          updated_ts=EXCLUDED.updated_ts
        """,
        node_id,
        node_type,
        props,
        now,
    )


async def upsert_edge(src_id: str, dst_id: str, edge_type: str, properties: Dict[str, Any] | None = None) -> None:
    if edge_type not in STANDARD_EDGE_TYPES:
        pass
    now = float(time.time())
    props = json.dumps(properties or {})
    await postgres.execute(
        """
        INSERT INTO graph_edges (src_id, dst_id, edge_type, properties, created_ts)
        VALUES ($1,$2,$3,$4,$5)
        ON CONFLICT (src_id,dst_id,edge_type) DO UPDATE SET
          properties=EXCLUDED.properties
        """,
        src_id,
        dst_id,
        edge_type,
        props,
        now,
    )


async def bulk_upsert_nodes(nodes: Iterable[tuple[str, str, Dict[str, Any] | None]]):
    for nid, ntype, props in nodes:
        try:
            await upsert_node(nid, ntype, props)
        except Exception:
            continue


async def bulk_upsert_edges(edges: Iterable[tuple[str, str, str, Dict[str, Any] | None]]):
    for sid, did, etype, props in edges:
        try:
            await upsert_edge(sid, did, etype, props)
        except Exception:
            continue


async def get_node(node_id: str) -> Optional[Dict[str, Any]]:
    rows = await postgres.fetch("SELECT * FROM graph_nodes WHERE id=$1", node_id)
    return dict(rows[0]) if rows else None


async def neighbors(node_id: str, direction: str = "both", edge_type: str | None = None, limit: int = 100) -> List[Dict[str, Any]]:
    clauses = []
    args: list[Any] = [node_id]
    sql_parts: list[str] = []
    if direction in ("out", "both"):
        c = "ge.src_id=$1" if direction == "out" else "ge.src_id=$1"
    if direction == "out":
        sql_parts.append("SELECT ge.dst_id AS neighbor_id, ge.edge_type, ge.properties FROM graph_edges ge WHERE ge.src_id=$1")
    elif direction == "in":
        sql_parts.append("SELECT ge.src_id AS neighbor_id, ge.edge_type, ge.properties FROM graph_edges ge WHERE ge.dst_id=$1")
    else:  # both
        sql_parts.append(
            "SELECT ge.dst_id AS neighbor_id, ge.edge_type, ge.properties FROM graph_edges ge WHERE ge.src_id=$1"
        )
        sql_parts.append(
            "SELECT ge.src_id AS neighbor_id, ge.edge_type, ge.properties FROM graph_edges ge WHERE ge.dst_id=$1"
        )
    base_sql = " UNION ALL ".join(sql_parts)
    if edge_type:
        base_sql = base_sql.replace(" WHERE ", f" WHERE edge_type='{edge_type}' AND ")
    base_sql += " LIMIT $2"
    args.append(limit)
    rows = await postgres.fetch(base_sql, *args)
    return [dict(r) for r in rows]


async def search_knowledge_articles(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    # Simple ILIKE search on title / content fields inside properties JSON.
    # Postgres syntax: properties->>'title'
    q = f"%{query.lower()}%"
    rows = await postgres.fetch(
        """
        SELECT id, properties->>'title' AS title, properties->>'summary' AS summary
        FROM graph_nodes
        WHERE node_type='KNOWLEDGE_ARTICLE' AND (lower(properties->>'title') LIKE $1 OR lower(properties->>'body') LIKE $1)
        ORDER BY updated_ts DESC
        LIMIT $2
        """,
        q,
        limit,
    )
    return [dict(r) for r in rows]


async def upsert_knowledge_article(slug: str, title: str, body: str, summary: str | None = None, tags: list[str] | None = None):
    props = {
        "title": title,
        "body": body,
        "summary": summary or (body[:240] + ("..." if len(body) > 240 else "")),
        "tags": tags or [],
        "slug": slug,
    }
    await upsert_node(f"ka:{slug}", "KNOWLEDGE_ARTICLE", props)


__all__ = [
    "upsert_node",
    "upsert_edge",
    "bulk_upsert_nodes",
    "bulk_upsert_edges",
    "get_node",
    "neighbors",
    "search_knowledge_articles",
    "upsert_knowledge_article",
    "STANDARD_NODE_TYPES",
    "STANDARD_EDGE_TYPES",
]
