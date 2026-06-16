-- ============================================================
-- 019_module_b_gaps.sql — Water access, CAPEX breakdown, Attestation plan
-- ============================================================

-- Water access infrastructure per location
CREATE TABLE IF NOT EXISTS water_access (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    source_type VARCHAR(100) NOT NULL, -- borehole, river, rainwater_harvesting, dam, piped, well, spring
    source_name VARCHAR(255),
    capacity_liters NUMERIC(12,2),
    reliability_score NUMERIC(5,2), -- 0-100: uptime/consistency
    quality_score NUMERIC(5,2), -- 0-100: potability/treatment
    distance_km NUMERIC(8,2), -- distance from farm
    monthly_cost_usd NUMERIC(10,2),
    status VARCHAR(50) DEFAULT 'active', -- active, inactive, maintenance
    last_inspection_date DATE,
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_water_access_location ON water_access(location_id);

-- Structured capital expenditure breakdown (replaces flat $200/ha estimate)
CREATE TABLE IF NOT EXISTS capex_breakdown (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    category VARCHAR(100) NOT NULL, -- setup, equipment, infrastructure, maintenance, working_capital
    subcategory VARCHAR(100), -- irrigation, storage, processing, transport, land_prep, fencing
    description TEXT,
    amount_usd NUMERIC(15,2) NOT NULL,
    useful_life_years INTEGER, -- depreciation horizon
    annual_depreciation_usd NUMERIC(12,2),
    is_recurring BOOLEAN DEFAULT FALSE, -- TRUE = ongoing capex, FALSE = one-time
    frequency VARCHAR(50), -- annual, seasonal, monthly (for recurring)
    source VARCHAR(100), -- estimate, quote, historical, benchmark
    confidence NUMERIC(3,2), -- 0-1: how reliable is this number
    period_start DATE,
    period_end DATE,
    status VARCHAR(50) DEFAULT 'draft', -- draft, verified, published
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_capex_location ON capex_breakdown(location_id);
CREATE INDEX IF NOT EXISTS idx_capex_category ON capex_breakdown(category);

-- Attestation and compliance plan per location
CREATE TABLE IF NOT EXISTS attestation_plan (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    attestation_type VARCHAR(100) NOT NULL, -- soil_carbon, biodiversity, water_stewardship, fair_labor, organic, carbon_credits
    target_date DATE,
    status VARCHAR(50) DEFAULT 'planned', -- planned, in_progress, submitted, achieved, expired
    schema_uid VARCHAR(66), -- EAS schema UID if registered
    attester_address VARCHAR(42), -- expected attester wallet
    estimated_cost_usd NUMERIC(10,2),
    estimated_value_usd NUMERIC(10,2), -- expected revenue/value from attestation
    documentation_urls TEXT[],
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_attestation_plan_location ON attestation_plan(location_id);
