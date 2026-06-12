-- ============================================================
-- 010_market_data.sql — External market/price data
-- ============================================================

CREATE TABLE IF NOT EXISTS price_observation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    crop_id UUID REFERENCES crop(id),
    commodity_code VARCHAR(50),
    market_name VARCHAR(100),
    price_date DATE NOT NULL,
    price_per_unit NUMERIC(12,4),
    unit VARCHAR(50),
    currency VARCHAR(10) DEFAULT 'USD',
    source VARCHAR(100),
    source_url TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_price_obs_crop_date ON price_observation(crop_id, price_date);
CREATE INDEX IF NOT EXISTS idx_price_obs_commodity ON price_observation(commodity_code, price_date);
CREATE INDEX IF NOT EXISTS idx_price_obs_source ON price_observation(source, price_date);
