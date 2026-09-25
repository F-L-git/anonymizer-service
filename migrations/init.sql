-- Initial schema for anonymizer service

CREATE TABLE IF NOT EXISTS processed_requests (
    id BIGSERIAL PRIMARY KEY,
    request_id VARCHAR(64) UNIQUE NOT NULL,
    client_id VARCHAR(128),
    original_hash VARCHAR(64) NOT NULL,
    original_length INTEGER NOT NULL,
    anonymized_length INTEGER NOT NULL,
    detections_count INTEGER DEFAULT 0,
    detections JSONB,
    stats JSONB,
    processing_time_ms DOUBLE PRECISION DEFAULT 0.0,
    cache_hit BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_processed_requests_hash ON processed_requests(original_hash);
CREATE INDEX IF NOT EXISTS idx_processed_requests_client ON processed_requests(client_id);
CREATE INDEX IF NOT EXISTS idx_processed_requests_created ON processed_requests(created_at);

CREATE TABLE IF NOT EXISTS rule_configs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(64) UNIQUE NOT NULL,
    type VARCHAR(64) NOT NULL,
    pattern TEXT NOT NULL,
    mask_strategy VARCHAR(32) DEFAULT 'full_mask',
    priority INTEGER DEFAULT 100,
    enabled BOOLEAN DEFAULT TRUE,
    description TEXT,
    example TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS usage_stats (
    id BIGSERIAL PRIMARY KEY,
    date TIMESTAMPTZ NOT NULL,
    total_requests INTEGER DEFAULT 0,
    total_detections INTEGER DEFAULT 0,
    detections_by_type JSONB,
    avg_processing_ms DOUBLE PRECISION DEFAULT 0.0,
    cache_hits INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_usage_stats_date ON usage_stats(date);
