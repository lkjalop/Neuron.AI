-- Migration 0008: Asset feature snapshot store for anomaly & forecasting
-- Creates table to hold per-asset aggregated metrics over time.

CREATE TABLE IF NOT EXISTS asset_feature_snapshots (
    asset_id TEXT NOT NULL,
    snapshot_ts DOUBLE PRECISION NOT NULL,
    open_findings_total INT NOT NULL,
    open_critical INT NOT NULL,
    open_high INT NOT NULL,
    open_medium INT NOT NULL,
    open_low INT NOT NULL,
    exploit_exposed INT NOT NULL, -- count of open findings with exploit available
    exposure_score DOUBLE PRECISION NOT NULL, -- simple weighted severity score
    new_findings_24h INT NOT NULL,
    closed_findings_24h INT NOT NULL,
    reopened_7d INT NOT NULL,
    avg_age_open_hours DOUBLE PRECISION,
    mttr_hours DOUBLE PRECISION,
    PRIMARY KEY (asset_id, snapshot_ts)
);
CREATE INDEX IF NOT EXISTS asset_feature_snapshots_ts_idx ON asset_feature_snapshots(snapshot_ts);
