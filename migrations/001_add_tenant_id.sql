-- Migration: Add tenant_id columns to core tables (idempotent best-effort)
-- NOTE: SQLite lacks ALTER COLUMN rename; we add new column if missing.

-- retrieval_chunks: add tenant_id if not exists; retain legacy tenant column for back-compat.
ALTER TABLE retrieval_chunks ADD COLUMN tenant_id TEXT;

-- Future tables (placeholders): assets, vulnerabilities, detections, reports
ALTER TABLE assets ADD COLUMN tenant_id TEXT;
ALTER TABLE vulnerabilities ADD COLUMN tenant_id TEXT;
ALTER TABLE detections ADD COLUMN tenant_id TEXT;
ALTER TABLE reports ADD COLUMN tenant_id TEXT;

-- Optional: param_store scoping
ALTER TABLE param_store ADD COLUMN tenant_id TEXT;
