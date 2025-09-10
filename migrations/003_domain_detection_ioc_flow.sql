-- Migration 003: detection / ioc / flow lightweight tables
-- Compatible with SQLite and Postgres (types simplified)
CREATE TABLE IF NOT EXISTS detection (
  id TEXT PRIMARY KEY,
  tenant_id TEXT,
  asset_id TEXT,
  ts REAL,
  tactic TEXT,
  technique TEXT,
  category TEXT,
  severity INTEGER,
  process_id TEXT,
  parent_process_id TEXT,
  command_line TEXT,
  hash_sha256 TEXT,
  source TEXT,
  ingested_at REAL,
  raw_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_detection_ts ON detection(ts);
CREATE INDEX IF NOT EXISTS idx_detection_tenant_tactic ON detection(tenant_id, tactic);

CREATE TABLE IF NOT EXISTS ioc (
  id TEXT PRIMARY KEY,
  tenant_id TEXT,
  type TEXT,
  value TEXT,
  first_seen REAL,
  last_seen REAL,
  confidence REAL,
  sources TEXT,
  tags TEXT,
  revoked INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_ioc_value ON ioc(value);
CREATE INDEX IF NOT EXISTS idx_ioc_tenant_type ON ioc(tenant_id, type);

CREATE TABLE IF NOT EXISTS flow (
  id TEXT PRIMARY KEY,
  tenant_id TEXT,
  src_asset TEXT,
  dst_asset TEXT,
  first_seen REAL,
  last_seen REAL,
  bytes_total REAL,
  flow_count INTEGER,
  period_signature TEXT,
  direction TEXT,
  proto TEXT
);
CREATE INDEX IF NOT EXISTS idx_flow_assets ON flow(src_asset, dst_asset);
CREATE INDEX IF NOT EXISTS idx_flow_tenant ON flow(tenant_id);
