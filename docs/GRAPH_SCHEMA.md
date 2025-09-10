# Graph & Knowledge Layer Schema (Batch 2)

## Overview
The graph layer represents interconnected security knowledge blending:
* Technical findings (vulnerabilities, assets)
* Threat intelligence (attack patterns)
* Governance (controls, procedures)
* Operational knowledge (SOC FAQs, how‑tos, runbooks)
* Remediation tasks

## Relational Backing
Two core tables (see inline DDL in `storage/graph_store.py` for authoritative definition):
```
graph_nodes(id TEXT PRIMARY KEY,
            node_type TEXT,
            properties JSONB,
            created_ts DOUBLE PRECISION,
            updated_ts DOUBLE PRECISION)
graph_edges(src_id TEXT,
            dst_id TEXT,
            edge_type TEXT,
            properties JSONB,
            created_ts DOUBLE PRECISION,
            PRIMARY KEY (src_id,dst_id,edge_type))
```

## Node Types
| Type | Description | ID Convention |
|------|-------------|---------------|
| VULNERABILITY | CVE or vendor issue | `vuln:CVE-YYYY-NNNN` |
| ASSET | Host / app / service | `asset:<uuid|name>` |
| KNOWLEDGE_ARTICLE | SOC internal guidance | `ka:<slug>` |
| PROCEDURE | Playbook step sequence | `proc:<slug>` |
| CONTROL | Framework control (CIS/NIST) | `ctrl:<framework>:<id>` |
| ATTACK_PATTERN | MITRE ATT&CK technique / CAPEC | `attk:T1059` |
| REMEDIATION_TASK | Actionable fix unit | `task:<uuid>` |

## Edge Types
| Edge | Direction | Meaning |
|------|-----------|---------|
| EXPLOITS | ATTACK_PATTERN -> VULNERABILITY | Pattern exploits vulnerability |
| AFFECTS | VULNERABILITY -> ASSET | Vulnerability present on asset |
| MITIGATES | CONTROL -> VULNERABILITY | Control reduces likelihood/impact |
| IMPLEMENTS | PROCEDURE -> CONTROL | Procedure operationalizes control |
| RELATES_TO | (ANY allowed) -> (ANY) | General association (knowledge, contextual) |
| REMEDIATES | REMEDIATION_TASK -> VULNERABILITY | Task addresses vulnerability |

## Future Extensions
* Vector embeddings table `graph_node_embeddings(node_id, embedding VECTOR, model_version)` for semantic expansion.
* Path queries with weighted traversal (risk scoring by propagation).
* Temporal edge validity for change modelling.

## Ingestion Pipeline (Knowledge Articles)
1. `scripts/ingest_docs_to_knowledge_graph.py` scans markdown docs.
2. Each file becomes a `KNOWLEDGE_ARTICLE` node (slug from title).
3. Later batches add auto-linking (NER to detect CVE IDs, control ids, technique IDs and create `RELATES_TO` edges).

## Agent Roles (Planned)
| Agent | Responsibility |
|-------|----------------|
| Graph Indexer | Maintains node/edge set from new sources |
| Enrichment Agent | Links CVEs to ATT&CK techniques & controls |
| Remediation Planner | Generates REMEDIATION_TASK nodes & edges |
| NLP Query Agent | Natural language to structured graph traversals |
| Drift Auditor | Detects stale / orphaned nodes & cleans |

## Validation Strategy
* Referential integrity: edges referencing non-existent nodes fail insert (FK constraints).
* Node property schema sampling: periodic JSON schema validation (future).
* Edge cardinality checks for critical types (e.g., MITIGATES should not create duplicate semantics beyond PK uniqueness).

## Migration Considerations
* Initial graph tables are additive; no existing contract impact.
* Ensure creation precedes any ingestion or tests using the graph layer.

---
Batch 2 deliverable: foundational graph persistence + knowledge ingestion script.
