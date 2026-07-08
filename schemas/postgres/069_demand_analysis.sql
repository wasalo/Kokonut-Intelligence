-- 069_demand_analysis.sql
-- Demand Analysis & Demand Sizing: Buyer signals, forecasts, market sizing, trends, segmentation

BEGIN;

-- ============================================================================
-- BUYER DEMAND SIGNAL
-- ============================================================================

CREATE TABLE IF NOT EXISTS buyer_demand_signal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    partner_id UUID REFERENCES partner(id) ON DELETE SET NULL,
    crop_id UUID REFERENCES crop(id) ON DELETE SET NULL,
    buyer_name VARCHAR(255),
    buyer_type VARCHAR(100)
        CHECK (buyer_type IN ('processor', 'direct', 'market', 'restaurant', 'retailer', 'export', 'cooperative', 'other')),
    signal_type VARCHAR(100) NOT NULL
        CHECK (signal_type IN ('verbal_intent', 'written_order', 'purchase_order', 'forecast_request', 'recurring_order')),
    signal_date DATE NOT NULL DEFAULT CURRENT_DATE,
    expected_delivery_start DATE,
    expected_delivery_end DATE,
    quantity_requested NUMERIC(12,4),
    unit VARCHAR(50),
    price_offered NUMERIC(12,4),
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    recurring BOOLEAN NOT NULL DEFAULT FALSE,
    recurrence_pattern VARCHAR(100),
    reliability_score NUMERIC(5,2),
    commitment_level VARCHAR(50)
        CHECK (commitment_level IN ('firm', 'probable', 'possible', 'exploratory')),
    notes TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected')),
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'demand-analysis-v1',
    source_system TEXT,
    source_id TEXT,
    source_raw JSONB,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_demand_signal_location ON buyer_demand_signal(location_id);
CREATE INDEX IF NOT EXISTS idx_demand_signal_partner ON buyer_demand_signal(partner_id);
CREATE INDEX IF NOT EXISTS idx_demand_signal_crop ON buyer_demand_signal(crop_id);
CREATE INDEX IF NOT EXISTS idx_demand_signal_date ON buyer_demand_signal(signal_date);
CREATE INDEX IF NOT EXISTS idx_demand_signal_type ON buyer_demand_signal(signal_type);
CREATE INDEX IF NOT EXISTS idx_demand_signal_status ON buyer_demand_signal(status);
CREATE INDEX IF NOT EXISTS idx_demand_signal_delivery ON buyer_demand_signal(expected_delivery_start, expected_delivery_end);

CREATE TRIGGER trg_demand_signal_updated_at
    BEFORE UPDATE ON buyer_demand_signal
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE buyer_demand_signal IS 'Buyer intent, future orders, and demand forecasts from buyers';

-- ============================================================================
-- DEMAND FORECAST
-- ============================================================================

CREATE TABLE IF NOT EXISTS demand_forecast (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    crop_id UUID REFERENCES crop(id) ON DELETE SET NULL,
    forecast_type VARCHAR(100) NOT NULL
        CHECK (forecast_type IN ('time_series', 'buyer_pipeline', 'seasonal_decomposition', 'hybrid')),
    forecast_period_start DATE NOT NULL,
    forecast_period_end DATE NOT NULL,
    predicted_quantity NUMERIC(12,4) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    predicted_revenue_usd NUMERIC(15,2),
    confidence_low NUMERIC(12,4),
    confidence_high NUMERIC(12,4),
    confidence_level NUMERIC(5,2) DEFAULT 0.90,
    seasonal_index NUMERIC(8,4),
    trend_slope NUMERIC(8,4),
    model_name VARCHAR(100),
    model_version VARCHAR(50),
    training_data_points INT,
    mape_pct NUMERIC(8,4),
    inputs JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published')),
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    schema_version VARCHAR(50) DEFAULT 'demand-analysis-v1',
    source_system TEXT,
    source_id TEXT,
    source_raw JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_demand_forecast_location ON demand_forecast(location_id);
CREATE INDEX IF NOT EXISTS idx_demand_forecast_crop ON demand_forecast(crop_id);
CREATE INDEX IF NOT EXISTS idx_demand_forecast_period ON demand_forecast(forecast_period_start, forecast_period_end);
CREATE INDEX IF NOT EXISTS idx_demand_forecast_type ON demand_forecast(forecast_type);
CREATE INDEX IF NOT EXISTS idx_demand_forecast_status ON demand_forecast(status);

CREATE TRIGGER trg_demand_forecast_updated_at
    BEFORE UPDATE ON demand_forecast
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE demand_forecast IS 'Predicted future demand by crop, buyer segment, and period';

-- ============================================================================
-- MARKET SIZE ESTIMATE
-- ============================================================================

CREATE TABLE IF NOT EXISTS market_size_estimate (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    crop_id UUID REFERENCES crop(id) ON DELETE SET NULL,
    market_name VARCHAR(255),
    market_scope VARCHAR(100) NOT NULL
        CHECK (market_scope IN ('local', 'regional', 'national', 'international')),
    tam_value NUMERIC(15,2),
    tam_unit VARCHAR(50),
    tam_source TEXT,
    sam_value NUMERIC(15,2),
    sam_unit VARCHAR(50),
    sam_source TEXT,
    som_value NUMERIC(15,2),
    som_unit VARCHAR(50),
    som_source TEXT,
    market_penetration_pct NUMERIC(8,4),
    market_share_pct NUMERIC(8,4),
    annual_growth_rate_pct NUMERIC(8,4),
    growth_source TEXT,
    estimation_method VARCHAR(100),
    confidence_level VARCHAR(50),
    assessment_date DATE,
    period_start DATE,
    period_end DATE,
    notes TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published')),
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    schema_version VARCHAR(50) DEFAULT 'demand-analysis-v1',
    source_system TEXT,
    source_id TEXT,
    source_raw JSONB,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_market_size_location ON market_size_estimate(location_id);
CREATE INDEX IF NOT EXISTS idx_market_size_crop ON market_size_estimate(crop_id);
CREATE INDEX IF NOT EXISTS idx_market_size_scope ON market_size_estimate(market_scope);
CREATE INDEX IF NOT EXISTS idx_market_size_status ON market_size_estimate(status);
CREATE INDEX IF NOT EXISTS idx_market_size_period ON market_size_estimate(period_start, period_end);

CREATE TRIGGER trg_market_size_updated_at
    BEFORE UPDATE ON market_size_estimate
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE market_size_estimate IS 'Market sizing (TAM/SAM/SOM) per crop per region';

-- ============================================================================
-- DEMAND TREND
-- ============================================================================

CREATE TABLE IF NOT EXISTS demand_trend (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    crop_id UUID REFERENCES crop(id) ON DELETE SET NULL,
    analysis_type VARCHAR(100) NOT NULL
        CHECK (analysis_type IN ('seasonal_pattern', 'price_elasticity', 'moving_average', 'trend_decomposition')),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    month_of_year INT,
    seasonal_index NUMERIC(8,4),
    seasonal_amplitude NUMERIC(8,4),
    price_elasticity NUMERIC(8,4),
    cross_price_elasticity NUMERIC(8,4),
    reference_crop_id UUID REFERENCES crop(id),
    trend_direction VARCHAR(50),
    trend_slope NUMERIC(8,4),
    trend_r_squared NUMERIC(6,4),
    moving_avg_3m NUMERIC(12,4),
    moving_avg_6m NUMERIC(12,4),
    moving_avg_12m NUMERIC(12,4),
    avg_monthly_demand NUMERIC(12,4),
    peak_month INT,
    trough_month INT,
    coefficient_of_variation NUMERIC(8,4),
    model_name VARCHAR(100),
    data_points INT,
    calculation_version VARCHAR(20),
    inputs JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published')),
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_demand_trend_location ON demand_trend(location_id);
CREATE INDEX IF NOT EXISTS idx_demand_trend_crop ON demand_trend(crop_id);
CREATE INDEX IF NOT EXISTS idx_demand_trend_type ON demand_trend(analysis_type);
CREATE INDEX IF NOT EXISTS idx_demand_trend_period ON demand_trend(period_start, period_end);

CREATE TRIGGER trg_demand_trend_updated_at
    BEFORE UPDATE ON demand_trend
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE demand_trend IS 'Seasonal patterns, price elasticity, trend decomposition for demand analysis';

-- ============================================================================
-- PRODUCTION MARKET MATCH
-- ============================================================================

CREATE TABLE IF NOT EXISTS production_market_match (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    crop_id UUID REFERENCES crop(id) ON DELETE SET NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    projected_production_tonnes NUMERIC(12,4),
    confirmed_supply_tonnes NUMERIC(12,4),
    supply_source VARCHAR(100),
    confirmed_demand_tonnes NUMERIC(12,4),
    pipeline_demand_tonnes NUMERIC(12,4),
    total_demand_tonnes NUMERIC(12,4),
    demand_source VARCHAR(100),
    supply_demand_gap_tonnes NUMERIC(12,4),
    gap_pct NUMERIC(8,4),
    demand_coverage_pct NUMERIC(8,4),
    unallocated_tonnes NUMERIC(12,4),
    unfulfilled_demand_tonnes NUMERIC(12,4),
    estimated_revenue_at_fill NUMERIC(15,2),
    revenue_gap_usd NUMERIC(15,2),
    calculation_version VARCHAR(20),
    inputs JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published')),
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_pmm_location ON production_market_match(location_id);
CREATE INDEX IF NOT EXISTS idx_pmm_crop ON production_market_match(crop_id);
CREATE INDEX IF NOT EXISTS idx_pmm_period ON production_market_match(period_start, period_end);

CREATE TRIGGER trg_pmm_updated_at
    BEFORE UPDATE ON production_market_match
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE production_market_match IS 'Supply-demand gap analysis matching production capacity to buyer demand';

-- ============================================================================
-- BUYER SEGMENT
-- ============================================================================

CREATE TABLE IF NOT EXISTS buyer_segment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    segment_name VARCHAR(255) NOT NULL,
    segment_type VARCHAR(100) NOT NULL
        CHECK (segment_type IN ('value_based', 'behavior_based', 'need_based', 'tier_based')),
    criteria JSONB NOT NULL DEFAULT '{}'::jsonb,
    description TEXT,
    buyer_count INT,
    total_revenue_usd NUMERIC(15,2),
    avg_order_value NUMERIC(12,4),
    avg_payment_days NUMERIC(8,2),
    repeat_purchase_rate NUMERIC(5,2),
    growth_rate_pct NUMERIC(8,4),
    segment_value VARCHAR(50)
        CHECK (segment_value IN ('high_value', 'medium_value', 'low_value', 'potential', 'at_risk', 'churned')),
    trend_direction VARCHAR(50),
    assessment_date DATE,
    period_start DATE,
    period_end DATE,
    notes TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published')),
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_buyer_segment_location ON buyer_segment(location_id);
CREATE INDEX IF NOT EXISTS idx_buyer_segment_type ON buyer_segment(segment_type);
CREATE INDEX IF NOT EXISTS idx_buyer_segment_value ON buyer_segment(segment_value);

CREATE TRIGGER trg_buyer_segment_updated_at
    BEFORE UPDATE ON buyer_segment
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE buyer_segment IS 'Buyer behavioral segmentation by value, behavior, and retention';

-- ============================================================================
-- VIEWS
-- ============================================================================

-- 1. Public demand forecast
CREATE OR REPLACE VIEW v_public_demand_forecast AS
SELECT
    df.id AS forecast_id,
    df.location_id,
    c.name AS crop_name,
    df.forecast_type,
    df.forecast_period_start,
    df.forecast_period_end,
    df.predicted_quantity,
    df.unit,
    df.predicted_revenue_usd,
    df.confidence_low,
    df.confidence_high,
    df.seasonal_index,
    df.trend_slope,
    df.model_name,
    df.mape_pct,
    df.status,
    df.created_at
FROM demand_forecast df
LEFT JOIN crop c ON df.crop_id = c.id
WHERE df.status IN ('verified', 'published');

-- 2. Public buyer demand signals
CREATE OR REPLACE VIEW v_public_buyer_demand_signals AS
SELECT
    bds.id AS signal_id,
    bds.location_id,
    COALESCE(p.name, bds.buyer_name, 'Unknown') AS buyer_name,
    bds.buyer_type,
    c.name AS crop_name,
    bds.signal_type,
    bds.signal_date,
    bds.expected_delivery_start,
    bds.expected_delivery_end,
    bds.quantity_requested,
    bds.unit,
    bds.price_offered,
    bds.commitment_level,
    bds.recurring,
    bds.recurrence_pattern,
    bds.status,
    bds.created_at
FROM buyer_demand_signal bds
LEFT JOIN partner p ON bds.partner_id = p.id
LEFT JOIN crop c ON bds.crop_id = c.id
WHERE bds.status IN ('verified', 'published');

-- 3. Public market size estimates
CREATE OR REPLACE VIEW v_public_market_size_estimates AS
SELECT
    mse.id AS estimate_id,
    mse.location_id,
    c.name AS crop_name,
    mse.market_name,
    mse.market_scope,
    mse.tam_value,
    mse.tam_unit,
    mse.sam_value,
    mse.sam_unit,
    mse.som_value,
    mse.som_unit,
    mse.market_penetration_pct,
    mse.market_share_pct,
    mse.annual_growth_rate_pct,
    mse.estimation_method,
    mse.confidence_level,
    mse.assessment_date,
    mse.period_start,
    mse.period_end,
    mse.status,
    mse.created_at
FROM market_size_estimate mse
LEFT JOIN crop c ON mse.crop_id = c.id
WHERE mse.status IN ('verified', 'published');

-- 4. Public demand trends
CREATE OR REPLACE VIEW v_public_demand_trends AS
SELECT
    dt.id AS trend_id,
    dt.location_id,
    c.name AS crop_name,
    dt.analysis_type,
    dt.period_start,
    dt.period_end,
    dt.month_of_year,
    dt.seasonal_index,
    dt.price_elasticity,
    dt.trend_direction,
    dt.trend_slope,
    dt.trend_r_squared,
    dt.moving_avg_3m,
    dt.moving_avg_6m,
    dt.moving_avg_12m,
    dt.avg_monthly_demand,
    dt.peak_month,
    dt.trough_month,
    dt.coefficient_of_variation,
    dt.status,
    dt.created_at
FROM demand_trend dt
LEFT JOIN crop c ON dt.crop_id = c.id
WHERE dt.status IN ('verified', 'published');

-- 5. Public buyer segments
CREATE OR REPLACE VIEW v_public_buyer_segments AS
SELECT
    bs.id AS segment_id,
    bs.location_id,
    bs.segment_name,
    bs.segment_type,
    bs.segment_value,
    bs.buyer_count,
    bs.total_revenue_usd,
    bs.avg_order_value,
    bs.avg_payment_days,
    bs.repeat_purchase_rate,
    bs.growth_rate_pct,
    bs.trend_direction,
    bs.assessment_date,
    bs.period_start,
    bs.period_end,
    bs.status,
    bs.created_at
FROM buyer_segment bs
WHERE bs.status IN ('verified', 'published');

-- 6. Public production-market match
CREATE OR REPLACE VIEW v_public_production_market_match AS
SELECT
    pmm.id AS match_id,
    pmm.location_id,
    c.name AS crop_name,
    pmm.period_start,
    pmm.period_end,
    pmm.projected_production_tonnes,
    pmm.confirmed_demand_tonnes,
    pmm.pipeline_demand_tonnes,
    pmm.total_demand_tonnes,
    pmm.supply_demand_gap_tonnes,
    pmm.gap_pct,
    pmm.demand_coverage_pct,
    pmm.unallocated_tonnes,
    pmm.unfulfilled_demand_tonnes,
    pmm.estimated_revenue_at_fill,
    pmm.revenue_gap_usd,
    pmm.status,
    pmm.created_at
FROM production_market_match pmm
LEFT JOIN crop c ON pmm.crop_id = c.id
WHERE pmm.status IN ('verified', 'published');

COMMIT;
