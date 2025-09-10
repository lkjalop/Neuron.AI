-- Domain tables (initial scaffold). SQLite flavor; upgrade path to PostgreSQL later.
CREATE TABLE IF NOT EXISTS assets (
  asset_id TEXT PRIMARY KEY,
  tenant_id TEXT,
  project_id TEXT,
  hostname TEXT,
  ip_address TEXT,
  platform TEXT,
  criticality INTEGER DEFAULT 0,
  tags TEXT,
  first_seen REAL,
  last_seen REAL
);
CREATE INDEX IF NOT EXISTS idx_assets_tenant_last_seen ON assets(tenant_id, last_seen);

CREATE TABLE IF NOT EXISTS vulnerabilities (
  vuln_id TEXT PRIMARY KEY,
  cve TEXT,
  title TEXT,
  severity TEXT,
  base_score REAL,
  exploit_likelihood REAL,
  published_date REAL,
  last_modified REAL
);

CREATE TABLE IF NOT EXISTS asset_vulns (
  asset_vuln_id TEXT PRIMARY KEY,
  tenant_id TEXT,
  project_id TEXT,
  asset_id TEXT,
  vuln_id TEXT,
  state TEXT DEFAULT 'open',
  introduced_at REAL,
  fixed_at REAL,
  sla_due_at REAL,
  suppress_reason TEXT,
  exploit_observed INTEGER DEFAULT 0,
  last_seen REAL
);
CREATE INDEX IF NOT EXISTS idx_asset_vulns_state ON asset_vulns(tenant_id, state);
CREATE INDEX IF NOT EXISTS idx_asset_vulns_sla ON asset_vulns(tenant_id, sla_due_at);

CREATE TABLE IF NOT EXISTS findings (
  finding_id TEXT PRIMARY KEY,
  tenant_id TEXT,
  project_id TEXT,
  type TEXT,
  title TEXT,
  description TEXT,
  severity TEXT,
  confidence REAL,
  citation_count INTEGER,
  citation_coverage REAL,
  unsupported_entities INTEGER,
  created_at REAL,
  updated_at REAL,
  status TEXT DEFAULT 'draft',
  source_context TEXT
);
CREATE INDEX IF NOT EXISTS idx_findings_status ON findings(tenant_id, status, severity);

CREATE TABLE IF NOT EXISTS ingestion_sources (
  source_id TEXT PRIMARY KEY,
  tenant_id TEXT,
  project_id TEXT,
  type TEXT,
  name TEXT,
  status TEXT,
  last_success REAL,
  last_attempt REAL,
  config TEXT
);

CREATE TABLE IF NOT EXISTS ingestion_events (
  event_id TEXT PRIMARY KEY,
  source_id TEXT,
  tenant_id TEXT,
  project_id TEXT,
  received_at REAL,
  raw_ref TEXT,
  size_bytes INTEGER
);
CREATE INDEX IF NOT EXISTS idx_ingestion_events_tenant ON ingestion_events(tenant_id, received_at);
