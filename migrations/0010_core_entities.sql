-- Migration 0010: Core entities (assets, findings, retrieval chunks, predictive artifacts)
CREATE TABLE IF NOT EXISTS assets (
  id TEXT PRIMARY KEY,
  tenant TEXT NOT NULL,
  type TEXT,
  meta JSONB NOT NULL DEFAULT '{}',
  created_ts DOUBLE PRECISION NOT NULL,
  updated_ts DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS assets_tenant_idx ON assets(tenant);

CREATE TABLE IF NOT EXISTS findings (
  id TEXT PRIMARY KEY,
  tenant TEXT NOT NULL,
  cve TEXT,
  severity TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  risk_json JSONB NOT NULL DEFAULT '{}',
  discovered_ts DOUBLE PRECISION NOT NULL,
  updated_ts DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS findings_tenant_idx ON findings(tenant);
CREATE INDEX IF NOT EXISTS findings_cve_idx ON findings(cve);

CREATE TABLE IF NOT EXISTS retrieval_chunks (
  id TEXT PRIMARY KEY,
  doc TEXT NOT NULL,
  chunk_id INT NOT NULL,
  hash TEXT,
  text TEXT,
  length INT,
  tenant TEXT,
  created_ts DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS retrieval_chunks_doc_idx ON retrieval_chunks(doc);
CREATE INDEX IF NOT EXISTS retrieval_chunks_tenant_idx ON retrieval_chunks(tenant);

CREATE TABLE IF NOT EXISTS predictive_artifacts (
  id TEXT PRIMARY KEY,
  model TEXT NOT NULL,
  sha256 TEXT,
  payload JSONB NOT NULL DEFAULT '{}',
  created_ts DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS predictive_artifacts_model_idx ON predictive_artifacts(model);
