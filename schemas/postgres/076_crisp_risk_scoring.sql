-- ============================================================
-- 076_crisp_risk_scoring.sql — CRISP risk scoring engine
-- ============================================================
-- Adapted from Solid World's SW-CRISP framework for internal
-- farm risk intelligence.  Five risk dimensions scored
-- per-location per-assessment-period with configurable weights
-- and a composite AAA-D rating.
-- ============================================================

-- 1. Per-dimension risk factor configuration (configurable per location)
CREATE TABLE IF NOT EXISTS crisp_risk_dimension (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dimension_key VARCHAR(50) NOT NULL UNIQUE,
    dimension_name VARCHAR(100) NOT NULL,
    description TEXT,
    default_weight NUMERIC(4,3) NOT NULL CHECK (default_weight >= 0 AND default_weight <= 1),
    data_sources TEXT[] DEFAULT '{}',
    scoring_methodology TEXT,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crisp_dimension_status ON crisp_risk_dimension(status);

ALTER TABLE crisp_risk_dimension DROP CONSTRAINT IF EXISTS chk_crisp_dimension_status;
ALTER TABLE crisp_risk_dimension ADD CONSTRAINT chk_crisp_dimension_status CHECK (status IN ('active', 'inactive'));

-- 2. Per-location weight overrides
CREATE TABLE IF NOT EXISTS crisp_location_weight (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    dimension_id UUID NOT NULL REFERENCES crisp_risk_dimension(id) ON DELETE CASCADE,
    weight NUMERIC(4,3) NOT NULL CHECK (weight >= 0 AND weight <= 1),
    override_reason TEXT,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(location_id, dimension_id)
);

CREATE INDEX IF NOT EXISTS idx_crisp_location_weight_location ON crisp_location_weight(location_id);
CREATE INDEX IF NOT EXISTS idx_crisp_location_weight_dimension ON crisp_location_weight(dimension_id);

ALTER TABLE crisp_location_weight DROP CONSTRAINT IF EXISTS chk_crisp_location_weight_status;
ALTER TABLE crisp_location_weight ADD CONSTRAINT chk_crisp_location_weight_status CHECK (status IN ('active', 'inactive'));

-- 3. Master risk assessment record per location per period
CREATE TABLE IF NOT EXISTS crisp_risk_assessment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    methodology_version VARCHAR(50) NOT NULL,
    carbon_yield_score NUMERIC(5,2) CHECK (carbon_yield_score IS NULL OR (carbon_yield_score >= 0 AND carbon_yield_score <= 100)),
    climate_score NUMERIC(5,2) CHECK (climate_score IS NULL OR (climate_score >= 0 AND climate_score <= 100)),
    policy_score NUMERIC(5,2) CHECK (policy_score IS NULL OR (policy_score >= 0 AND policy_score <= 100)),
    financial_score NUMERIC(5,2) CHECK (financial_score IS NULL OR (financial_score >= 0 AND financial_score <= 100)),
    implementation_score NUMERIC(5,2) CHECK (implementation_score IS NULL OR (implementation_score >= 0 AND implementation_score <= 100)),
    composite_score NUMERIC(5,2) CHECK (composite_score IS NULL OR (composite_score >= 0 AND composite_score <= 100)),
    rating VARCHAR(5),
    confidence_level VARCHAR(30),
    score_computed_at TIMESTAMPTZ,
    evidence_maturity_level INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    reviewer_notes TEXT,
    metadata JSONB DEFAULT '{}',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_by UUID,
    updated_by UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(location_id, period_start, period_end, methodology_version)
);

CREATE INDEX IF NOT EXISTS idx_crisp_assessment_location ON crisp_risk_assessment(location_id);
CREATE INDEX IF NOT EXISTS idx_crisp_assessment_farm ON crisp_risk_assessment(farm_id);
CREATE INDEX IF NOT EXISTS idx_crisp_assessment_period ON crisp_risk_assessment(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_crisp_assessment_rating ON crisp_risk_assessment(rating);
CREATE INDEX IF NOT EXISTS idx_crisp_assessment_status ON crisp_risk_assessment(status);

ALTER TABLE crisp_risk_assessment DROP CONSTRAINT IF EXISTS chk_crisp_assessment_lifecycle;
ALTER TABLE crisp_risk_assessment ADD CONSTRAINT chk_crisp_assessment_lifecycle CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE crisp_risk_assessment DROP CONSTRAINT IF EXISTS chk_crisp_assessment_period;
ALTER TABLE crisp_risk_assessment ADD CONSTRAINT chk_crisp_assessment_period CHECK (period_start <= period_end);

ALTER TABLE crisp_risk_assessment DROP CONSTRAINT IF EXISTS chk_crisp_assessment_confidence;
ALTER TABLE crisp_risk_assessment ADD CONSTRAINT chk_crisp_assessment_confidence CHECK (
    confidence_level IS NULL OR confidence_level IN ('high', 'moderate', 'low', 'insufficient_evidence')
);

ALTER TABLE crisp_risk_assessment DROP CONSTRAINT IF EXISTS chk_crisp_assessment_rating;
ALTER TABLE crisp_risk_assessment ADD CONSTRAINT chk_crisp_assessment_rating CHECK (
    rating IS NULL OR rating IN ('AAA', 'AA', 'A', 'B', 'C', 'D')
);

-- 4. Carbon yield risk detail
CREATE TABLE IF NOT EXISTS crisp_carbon_yield_risk (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id UUID NOT NULL REFERENCES crisp_risk_assessment(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    tree_inventory_snapshot JSONB,
    soil_carbon_snapshot JSONB,
    harvest_snapshot JSONB,
    allometric_source VARCHAR(255),
    growth_model_reference VARCHAR(255),
    planting_density_per_ha NUMERIC(10,2),
    mortality_rate_pct NUMERIC(5,2),
    ndvi_pre_project NUMERIC(5,3),
    scenario_minimum NUMERIC(12,4),
    scenario_realistic NUMERIC(12,4),
    scenario_optimistic NUMERIC(12,4),
    ex_ante_estimate NUMERIC(12,4),
    yield_unit VARCHAR(50) DEFAULT 'tonnes_co2e',
    yield_likelihood NUMERIC(5,4) CHECK (yield_likelihood IS NULL OR (yield_likelihood >= 0 AND yield_likelihood <= 1)),
    risk_score NUMERIC(5,2) CHECK (risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)),
    uncertainty_pct NUMERIC(5,2),
    carbon_pool_breakdown JSONB DEFAULT '{}',
    evidence_maturity_level INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crisp_cy_assessment ON crisp_carbon_yield_risk(assessment_id);
CREATE INDEX IF NOT EXISTS idx_crisp_cy_location ON crisp_carbon_yield_risk(location_id);

-- 5. Climate catastrophe risk detail
CREATE TABLE IF NOT EXISTS crisp_climate_risk (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id UUID NOT NULL REFERENCES crisp_risk_assessment(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    drought_risk_score NUMERIC(4,2) CHECK (drought_risk_score IS NULL OR (drought_risk_score >= 0 AND drought_risk_score <= 3)),
    flood_risk_score NUMERIC(4,2) CHECK (flood_risk_score IS NULL OR (flood_risk_score >= 0 AND flood_risk_score <= 3)),
    heatwave_risk_score NUMERIC(4,2) CHECK (heatwave_risk_score IS NULL OR (heatwave_risk_score >= 0 AND heatwave_risk_score <= 3)),
    fire_risk_score NUMERIC(4,2) CHECK (fire_risk_score IS NULL OR (fire_risk_score >= 0 AND fire_risk_score <= 3)),
    storm_risk_score NUMERIC(4,2) CHECK (storm_risk_score IS NULL OR (storm_risk_score >= 0 AND storm_risk_score <= 3)),
    water_stress_score NUMERIC(4,2) CHECK (water_stress_score IS NULL OR (water_stress_score >= 0 AND water_stress_score <= 3)),
    natural_risk_rating NUMERIC(5,2) CHECK (natural_risk_rating IS NULL OR (natural_risk_rating >= 0 AND natural_risk_rating <= 15)),
    mitigation_factor NUMERIC(4,2) DEFAULT 1.0 CHECK (mitigation_factor IS NULL OR (mitigation_factor >= 0 AND mitigation_factor <= 1)),
    climate_catastrophe_factor NUMERIC(5,4) CHECK (climate_catastrophe_factor IS NULL OR (climate_catastrophe_factor >= 0 AND climate_catastrophe_factor <= 1)),
    ssp_scenario VARCHAR(10) DEFAULT 'SSP2',
    risk_score NUMERIC(5,2) CHECK (risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)),
    historical_events JSONB DEFAULT '[]',
    climate_projections_source VARCHAR(255),
    evidence_maturity_level INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crisp_climate_assessment ON crisp_climate_risk(assessment_id);
CREATE INDEX IF NOT EXISTS idx_crisp_climate_location ON crisp_climate_risk(location_id);

ALTER TABLE crisp_climate_risk DROP CONSTRAINT IF EXISTS chk_crisp_climate_ssp;
ALTER TABLE crisp_climate_risk ADD CONSTRAINT chk_crisp_climate_ssp CHECK (
    ssp_scenario IN ('SSP1', 'SSP2', 'SSP5')
);

-- 6. Policy and legal risk detail
CREATE TABLE IF NOT EXISTS crisp_policy_risk (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id UUID NOT NULL REFERENCES crisp_risk_assessment(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    national_policy_score NUMERIC(4,2) CHECK (national_policy_score IS NULL OR (national_policy_score >= 0 AND national_policy_score <= 1)),
    article_6_score NUMERIC(4,2) CHECK (article_6_score IS NULL OR (article_6_score >= 0 AND article_6_score <= 1)),
    carbon_rights_score NUMERIC(4,2) CHECK (carbon_rights_score IS NULL OR (carbon_rights_score >= 0 AND carbon_rights_score <= 1)),
    land_tenure_score NUMERIC(4,2) CHECK (land_tenure_score IS NULL OR (land_tenure_score >= 0 AND land_tenure_score <= 1)),
    community_alignment_score NUMERIC(4,2) CHECK (community_alignment_score IS NULL OR (community_alignment_score >= 0 AND community_alignment_score <= 1)),
    certification_risk_score NUMERIC(4,2) CHECK (certification_risk_score IS NULL OR (certification_risk_score >= 0 AND certification_risk_score <= 1)),
    risk_score NUMERIC(5,2) CHECK (risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)),
    policy_indicators JSONB DEFAULT '{}',
    evidence_maturity_level INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crisp_policy_assessment ON crisp_policy_risk(assessment_id);
CREATE INDEX IF NOT EXISTS idx_crisp_policy_location ON crisp_policy_risk(location_id);

-- 7. Financial viability risk detail
CREATE TABLE IF NOT EXISTS crisp_financial_risk (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id UUID NOT NULL REFERENCES crisp_risk_assessment(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    break_even_year INTEGER,
    revenue_risk_factor NUMERIC(5,4) CHECK (revenue_risk_factor IS NULL OR (revenue_risk_factor >= 0 AND revenue_risk_factor <= 1)),
    cost_risk_factor NUMERIC(5,4) CHECK (cost_risk_factor IS NULL OR (cost_risk_factor >= 0 AND cost_risk_factor <= 1)),
    market_price_risk NUMERIC(5,4) CHECK (market_price_risk IS NULL OR (market_price_risk >= 0 AND market_price_risk <= 1)),
    liquidity_risk NUMERIC(5,4) CHECK (liquidity_risk IS NULL OR (liquidity_risk >= 0 AND liquidity_risk <= 1)),
    vintage_year INTEGER,
    financial_risk_factor NUMERIC(5,4) CHECK (financial_risk_factor IS NULL OR (financial_risk_factor >= 0 AND financial_risk_factor <= 1)),
    risk_score NUMERIC(5,2) CHECK (risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)),
    financial_snapshot JSONB DEFAULT '{}',
    evidence_maturity_level INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crisp_financial_assessment ON crisp_financial_risk(assessment_id);
CREATE INDEX IF NOT EXISTS idx_crisp_financial_location ON crisp_financial_risk(location_id);

-- 8. Implementation / project developer risk detail
CREATE TABLE IF NOT EXISTS crisp_implementation_risk (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id UUID NOT NULL REFERENCES crisp_risk_assessment(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    track_record_score NUMERIC(4,2) CHECK (track_record_score IS NULL OR (track_record_score >= 0 AND track_record_score <= 1)),
    team_strength_score NUMERIC(4,2) CHECK (team_strength_score IS NULL OR (team_strength_score >= 0 AND team_strength_score <= 1)),
    network_strength_score NUMERIC(4,2) CHECK (network_strength_score IS NULL OR (network_strength_score >= 0 AND network_strength_score <= 1)),
    community_alignment_score NUMERIC(4,2) CHECK (community_alignment_score IS NULL OR (community_alignment_score >= 0 AND community_alignment_score <= 1)),
    transparency_score NUMERIC(4,2) CHECK (transparency_score IS NULL OR (transparency_score >= 0 AND transparency_score <= 1)),
    risk_score NUMERIC(5,2) CHECK (risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)),
    implementation_evidence JSONB DEFAULT '{}',
    evidence_maturity_level INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crisp_impl_assessment ON crisp_implementation_risk(assessment_id);
CREATE INDEX IF NOT EXISTS idx_crisp_impl_location ON crisp_implementation_risk(location_id);

-- 9. Public composite view
CREATE OR REPLACE VIEW v_crisp_composite_rating AS
SELECT
    cra.id AS assessment_id,
    cra.location_id,
    l.name AS location_name,
    cra.farm_id,
    f.name AS farm_name,
    cra.period_start,
    cra.period_end,
    cra.carbon_yield_score,
    cra.climate_score,
    cra.policy_score,
    cra.financial_score,
    cra.implementation_score,
    cra.composite_score,
    cra.rating,
    cra.confidence_level,
    cra.methodology_version,
    cra.score_computed_at,
    cra.evidence_maturity_level,
    cra.status,
    COALESCE(clw_cy.weight, cd_cy.default_weight) AS carbon_yield_weight,
    COALESCE(clw_cl.weight, cd_cl.default_weight) AS climate_weight,
    COALESCE(clw_po.weight, cd_po.default_weight) AS policy_weight,
    COALESCE(clw_fin.weight, cd_fin.default_weight) AS financial_weight,
    COALESCE(clw_im.weight, cd_im.default_weight) AS implementation_weight
FROM crisp_risk_assessment cra
JOIN location l ON l.id = cra.location_id
LEFT JOIN farm f ON f.id = cra.farm_id
LEFT JOIN crisp_risk_dimension cd_cy ON cd_cy.dimension_key = 'carbon_yield'
LEFT JOIN crisp_risk_dimension cd_cl ON cd_cl.dimension_key = 'climate'
LEFT JOIN crisp_risk_dimension cd_po ON cd_po.dimension_key = 'policy'
LEFT JOIN crisp_risk_dimension cd_fin ON cd_fin.dimension_key = 'financial'
LEFT JOIN crisp_risk_dimension cd_im ON cd_im.dimension_key = 'implementation'
LEFT JOIN crisp_location_weight clw_cy ON clw_cy.location_id = cra.location_id AND clw_cy.dimension_id = cd_cy.id AND clw_cy.status = 'active'
LEFT JOIN crisp_location_weight clw_cl ON clw_cl.location_id = cra.location_id AND clw_cl.dimension_id = cd_cl.id AND clw_cl.status = 'active'
LEFT JOIN crisp_location_weight clw_po ON clw_po.location_id = cra.location_id AND clw_po.dimension_id = cd_po.id AND clw_po.status = 'active'
LEFT JOIN crisp_location_weight clw_fin ON clw_fin.location_id = cra.location_id AND clw_fin.dimension_id = cd_fin.id AND clw_fin.status = 'active'
LEFT JOIN crisp_location_weight clw_im ON clw_im.location_id = cra.location_id AND clw_im.dimension_id = cd_im.id AND clw_im.status = 'active'
WHERE cra.status = 'published';

-- 10. Internal latest-assessment view (draft through published)
CREATE OR REPLACE VIEW v_crisp_latest_assessment AS
SELECT DISTINCT ON (cra.location_id)
    cra.id AS assessment_id,
    cra.location_id,
    l.name AS location_name,
    cra.period_start,
    cra.period_end,
    cra.carbon_yield_score,
    cra.climate_score,
    cra.policy_score,
    cra.financial_score,
    cra.implementation_score,
    cra.composite_score,
    cra.rating,
    cra.confidence_level,
    cra.methodology_version,
    cra.score_computed_at,
    cra.status
FROM crisp_risk_assessment cra
JOIN location l ON l.id = cra.location_id
ORDER BY cra.location_id, cra.period_end DESC, cra.created_at DESC;
