-- ============================================================
-- 016_revenue_multiplier_config.sql — Configurable constants for revenue multiplier dimensions
-- ============================================================

CREATE TABLE IF NOT EXISTS revenue_multiplier_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value JSONB NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rm_config_key ON revenue_multiplier_config(config_key);
