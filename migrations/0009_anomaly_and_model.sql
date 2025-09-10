-- Migration 0009: Anomaly detection & model scoring schema
-- Provides storage for model metadata, asset-level scores, and discrete anomaly events.

CREATE TABLE IF NOT EXISTS model_runs (
    id TEXT PRIMARY KEY,
    model_type TEXT NOT NULL,          -- e.g. isolation_forest, tft_forecast, snn_similarity
    version TEXT NOT NULL,             -- semantic or hash of parameters
    started_ts DOUBLE PRECISION NOT NULL,
    completed_ts DOUBLE PRECISION,
    status TEXT NOT NULL DEFAULT 'running',
    params JSONB NOT NULL DEFAULT '{}',
    metrics JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS model_runs_type_idx ON model_runs(model_type);

CREATE TABLE IF NOT EXISTS asset_model_scores (
    model_run_id TEXT NOT NULL REFERENCES model_runs(id) ON DELETE CASCADE,
    asset_id TEXT NOT NULL,
    score DOUBLE PRECISION NOT NULL,
    rank INT,
    extra JSONB NOT NULL DEFAULT '{}',
    PRIMARY KEY (model_run_id, asset_id)
);
CREATE INDEX IF NOT EXISTS asset_model_scores_score_idx ON asset_model_scores(score);

CREATE TABLE IF NOT EXISTS anomaly_events (
    id TEXT PRIMARY KEY,
    model_run_id TEXT REFERENCES model_runs(id) ON DELETE SET NULL,
    asset_id TEXT,
    anomaly_type TEXT NOT NULL,        -- spike, drift, outlier, coverage_gap, forecast_deviation
    score DOUBLE PRECISION NOT NULL,
    severity TEXT,
    detected_ts DOUBLE PRECISION NOT NULL,
    window_start_ts DOUBLE PRECISION,
    window_end_ts DOUBLE PRECISION,
    context JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS anomaly_events_asset_idx ON anomaly_events(asset_id);
CREATE INDEX IF NOT EXISTS anomaly_events_type_idx ON anomaly_events(anomaly_type);
