-- Migration 0007: Graph, Embeddings, Dashboard, Reporting Support
-- Idempotent-ish: uses IF NOT EXISTS where possible (Postgres 9.6+ assumed)

CREATE TABLE IF NOT EXISTS graph_nodes (
    id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,
    properties JSONB NOT NULL DEFAULT '{}',
    created_ts DOUBLE PRECISION NOT NULL,
    updated_ts DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS graph_nodes_type_idx ON graph_nodes(node_type);

CREATE TABLE IF NOT EXISTS graph_edges (
    src_id TEXT NOT NULL,
    dst_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    properties JSONB NOT NULL DEFAULT '{}',
    created_ts DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (src_id, dst_id, edge_type)
);
CREATE INDEX IF NOT EXISTS graph_edges_type_idx ON graph_edges(edge_type);
CREATE INDEX IF NOT EXISTS graph_edges_dst_idx ON graph_edges(dst_id);

CREATE TABLE IF NOT EXISTS graph_node_embeddings (
    node_id TEXT PRIMARY KEY REFERENCES graph_nodes(id) ON DELETE CASCADE,
    model_version TEXT NOT NULL,
    dims INT NOT NULL,
    embedding JSONB NOT NULL,
    created_ts DOUBLE PRECISION NOT NULL
);

-- Dashboard snapshot cache
CREATE TABLE IF NOT EXISTS dashboard_cache (
    snapshot_type TEXT PRIMARY KEY,
    generated_ts DOUBLE PRECISION NOT NULL,
    data JSONB NOT NULL
);

-- Report runs metadata
CREATE TABLE IF NOT EXISTS report_runs (
    id TEXT PRIMARY KEY,
    report_type TEXT NOT NULL,
    generated_ts DOUBLE PRECISION NOT NULL,
    params JSONB NOT NULL DEFAULT '{}',
    artifact_path TEXT,
    status TEXT NOT NULL DEFAULT 'completed'
);
