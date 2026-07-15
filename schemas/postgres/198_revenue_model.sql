-- Migration 198: Revenue Model + Cost Structure
-- Phase 7B of BMC Sprint
--
-- Tables:
--   revenue_stream_definition  – Defines recurring revenue models
--   pricing_model              – Pricing tiers, per-unit, volume discounts
--   cost_structure             – Fixed vs variable cost classification
--   cost_driver                – What causes costs to change
--   break_even_analysis        – Break-even calculations and sensitivity

BEGIN;

-- ============================================================
-- 1. revenue_stream_definition
-- ============================================================
CREATE TABLE IF NOT EXISTS revenue_stream_definition (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    stream_name VARCHAR(255) NOT NULL,
    stream_type VARCHAR(50) NOT NULL
        CHECK (stream_type IN ('one_time', 'recurring', 'subscription', 'licensing', 'brokerage', 'advertising', 'grant', 'carbon_credit', 'biodiversity_credit')),
    product_service VARCHAR(255),
    description TEXT,
    currency VARCHAR(10) DEFAULT 'USD',
    estimated_annual_usd NUMERIC(12,2) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_rsd_location ON revenue_stream_definition(location_id);
CREATE INDEX IF NOT EXISTS idx_rsd_type ON revenue_stream_definition(stream_type);
CREATE INDEX IF NOT EXISTS idx_rsd_active ON revenue_stream_definition(is_active);

-- ============================================================
-- 2. pricing_model
-- ============================================================
CREATE TABLE IF NOT EXISTS pricing_model (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    revenue_stream_id UUID REFERENCES revenue_stream_definition(id) ON DELETE SET NULL,
    product_name VARCHAR(255) NOT NULL,
    pricing_type VARCHAR(50) NOT NULL
        CHECK (pricing_type IN ('per_unit', 'per_kg', 'per_hectare', 'subscription_tier', 'volume_discount', 'dynamic', 'flat_rate')),
    base_price NUMERIC(12,2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    unit VARCHAR(50),
    min_quantity NUMERIC(12,2) DEFAULT 0,
    max_quantity NUMERIC(12,2),
    volume_discount_pct NUMERIC(5,2) DEFAULT 0
        CHECK (volume_discount_pct >= 0 AND volume_discount_pct <= 100),
    tier_name VARCHAR(100),
    tier_description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_pm_location ON pricing_model(location_id);
CREATE INDEX IF NOT EXISTS idx_pm_stream ON pricing_model(revenue_stream_id);
CREATE INDEX IF NOT EXISTS idx_pm_type ON pricing_model(pricing_type);

-- ============================================================
-- 3. cost_structure
-- ============================================================
CREATE TABLE IF NOT EXISTS cost_structure (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    cost_category VARCHAR(100) NOT NULL,
    cost_subcategory VARCHAR(100),
    cost_type VARCHAR(20) NOT NULL CHECK (cost_type IN ('fixed', 'variable', 'semi_variable')),
    amount_usd NUMERIC(12,2) NOT NULL DEFAULT 0,
    frequency VARCHAR(50) DEFAULT 'monthly'
        CHECK (frequency IN ('one_time', 'daily', 'weekly', 'monthly', 'quarterly', 'annually')),
    period_start DATE,
    period_end DATE,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_cs_location ON cost_structure(location_id);
CREATE INDEX IF NOT EXISTS idx_cs_category ON cost_structure(cost_category);
CREATE INDEX IF NOT EXISTS idx_cs_type ON cost_structure(cost_type);

-- ============================================================
-- 4. cost_driver
-- ============================================================
CREATE TABLE IF NOT EXISTS cost_driver (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    cost_structure_id UUID REFERENCES cost_structure(id) ON DELETE SET NULL,
    driver_name VARCHAR(255) NOT NULL,
    driver_type VARCHAR(50) NOT NULL
        CHECK (driver_type IN ('volume', 'labor', 'input_price', 'weather', 'seasonal', 'regulatory', 'market')),
    sensitivity_pct NUMERIC(5,2) DEFAULT 0
        CHECK (sensitivity_pct >= -100 AND sensitivity_pct <= 100),
    description TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cd_location ON cost_driver(location_id);
CREATE INDEX IF NOT EXISTS idx_cd_structure ON cost_driver(cost_structure_id);
CREATE INDEX IF NOT EXISTS idx_cd_type ON cost_driver(driver_type);

-- ============================================================
-- 5. break_even_analysis
-- ============================================================
CREATE TABLE IF NOT EXISTS break_even_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    analysis_name VARCHAR(255) DEFAULT 'Default Analysis',
    total_fixed_costs NUMERIC(12,2) NOT NULL DEFAULT 0,
    variable_cost_per_unit NUMERIC(12,2) NOT NULL DEFAULT 0,
    price_per_unit NUMERIC(12,2) NOT NULL DEFAULT 0,
    break_even_units NUMERIC(12,2),
    break_even_revenue NUMERIC(12,2),
    contribution_margin NUMERIC(5,2),
    margin_of_safety_pct NUMERIC(5,2),
    operating_leverage NUMERIC(8,4),
    analysis_date DATE DEFAULT CURRENT_DATE,
    assumptions JSONB DEFAULT '{}',
    sensitivity_data JSONB DEFAULT '[]',
    status VARCHAR(50) DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published')),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_bea_location ON break_even_analysis(location_id);
CREATE INDEX IF NOT EXISTS idx_bea_status ON break_even_analysis(status);

-- ============================================================
-- Views
-- ============================================================

-- Revenue stream summary per location
CREATE OR REPLACE VIEW v_revenue_stream_summary AS
SELECT
    rsd.location_id,
    l.name AS location_name,
    COUNT(*) AS stream_count,
    SUM(rsd.estimated_annual_usd) AS total_estimated_annual,
    COUNT(*) FILTER (WHERE rsd.stream_type = 'subscription') AS subscription_streams,
    COUNT(*) FILTER (WHERE rsd.stream_type = 'carbon_credit') AS carbon_streams,
    COUNT(*) FILTER (WHERE rsd.stream_type = 'one_time') AS one_time_streams
FROM revenue_stream_definition rsd
JOIN location l ON l.id = rsd.location_id
WHERE rsd.is_active = TRUE
GROUP BY rsd.location_id, l.name;

-- Cost structure summary per location
CREATE OR REPLACE VIEW v_cost_structure_summary AS
SELECT
    cs.location_id,
    l.name AS location_name,
    SUM(cs.amount_usd) FILTER (WHERE cs.cost_type = 'fixed') AS total_fixed,
    SUM(cs.amount_usd) FILTER (WHERE cs.cost_type = 'variable') AS total_variable,
    SUM(cs.amount_usd) FILTER (WHERE cs.cost_type = 'semi_variable') AS total_semi_variable,
    SUM(cs.amount_usd) AS total_costs,
    COUNT(*) AS cost_line_count
FROM cost_structure cs
JOIN location l ON l.id = cs.location_id
WHERE cs.is_active = TRUE
GROUP BY cs.location_id, l.name;

-- Break-even summary per location
CREATE OR REPLACE VIEW v_break_even_summary AS
SELECT
    bea.location_id,
    l.name AS location_name,
    bea.analysis_name,
    bea.break_even_units,
    bea.break_even_revenue,
    bea.contribution_margin,
    bea.margin_of_safety_pct,
    bea.analysis_date
FROM break_even_analysis bea
JOIN location l ON l.id = bea.location_id
WHERE bea.status IN ('verified', 'published')
ORDER BY bea.analysis_date DESC;

COMMIT;
