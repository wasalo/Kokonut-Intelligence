-- Migration 204: Regional Readiness — Full Analytical Service
--
-- Tables:
--   readiness_dimension           -- Dimension config with default weights
--   readiness_location_weight     -- Per-location weight overrides
--   regional_assessment           -- Master assessment record
--   regional_dimension_score      -- Per-dimension detail scores
--   regional_benchmark            -- External/internal benchmarks
--
-- Views:
--   v_regional_composite          -- Latest assessment per location
--   v_regional_dimension_detail   -- All dimension scores
--   v_regional_benchmark_compare  -- Assessment vs benchmark

BEGIN;

-- ============================================================
-- 1. readiness_dimension -- dimension config
-- ============================================================
CREATE TABLE IF NOT EXISTS readiness_dimension (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dimension_key VARCHAR(50) NOT NULL UNIQUE,
    dimension_name VARCHAR(100) NOT NULL,
    description TEXT,
    default_weight NUMERIC(4,3) NOT NULL CHECK (default_weight >= 0 AND default_weight <= 1),
    data_sources TEXT[] DEFAULT '{}',
    scoring_methodology TEXT,
    status VARCHAR(50) DEFAULT 'active'
        CHECK (status IN ('active', 'deprecated')),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rd_key ON readiness_dimension(dimension_key);

DROP TRIGGER IF EXISTS trg_readiness_dimension_updated_at ON readiness_dimension;
CREATE TRIGGER trg_readiness_dimension_updated_at
    BEFORE UPDATE ON readiness_dimension
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE readiness_dimension IS 'Regional readiness dimension config with default weights';

-- ============================================================
-- 2. readiness_location_weight -- per-location overrides
-- ============================================================
CREATE TABLE IF NOT EXISTS readiness_location_weight (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    dimension_id UUID NOT NULL REFERENCES readiness_dimension(id) ON DELETE CASCADE,
    weight NUMERIC(4,3) NOT NULL CHECK (weight >= 0 AND weight <= 1),
    override_reason TEXT,
    status VARCHAR(50) DEFAULT 'active'
        CHECK (status IN ('active', 'deprecated')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(location_id, dimension_id)
);

CREATE INDEX IF NOT EXISTS idx_rlw_location ON readiness_location_weight(location_id);

DROP TRIGGER IF EXISTS trg_readiness_location_weight_updated_at ON readiness_location_weight;
CREATE TRIGGER trg_readiness_location_weight_updated_at
    BEFORE UPDATE ON readiness_location_weight
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE readiness_location_weight IS 'Per-location dimension weight overrides for regional readiness';

-- ============================================================
-- 3. regional_assessment -- master assessment record
-- ============================================================
CREATE TABLE IF NOT EXISTS regional_assessment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    title VARCHAR(200) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    methodology_version VARCHAR(50) NOT NULL DEFAULT 'v2026.07',
    composite_score NUMERIC(5,2) CHECK (composite_score >= 0 AND composite_score <= 100),
    rating VARCHAR(5) CHECK (rating IN ('A+', 'A', 'B', 'C', 'D')),
    confidence_level VARCHAR(30),
    infrastructure_score NUMERIC(5,2) CHECK (infrastructure_score >= 0 AND infrastructure_score <= 100),
    institutions_score NUMERIC(5,2) CHECK (institutions_score >= 0 AND institutions_score <= 100),
    market_access_score NUMERIC(5,2) CHECK (market_access_score >= 0 AND market_access_score <= 100),
    natural_capital_score NUMERIC(5,2) CHECK (natural_capital_score >= 0 AND natural_capital_score <= 100),
    policy_environment_score NUMERIC(5,2) CHECK (policy_environment_score >= 0 AND policy_environment_score <= 100),
    human_capital_score NUMERIC(5,2) CHECK (human_capital_score >= 0 AND human_capital_score <= 100),
    evidence_summary TEXT,
    uncertainty_notes TEXT,
    status VARCHAR(50) DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected')),
    metadata JSONB DEFAULT '{}',
    created_by UUID,
    updated_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(location_id, period_start, period_end, methodology_version)
);

CREATE INDEX IF NOT EXISTS idx_ra_location ON regional_assessment(location_id);
CREATE INDEX IF NOT EXISTS idx_ra_status ON regional_assessment(status);
CREATE INDEX IF NOT EXISTS idx_ra_rating ON regional_assessment(rating);

DROP TRIGGER IF EXISTS trg_regional_assessment_updated_at ON regional_assessment;
CREATE TRIGGER trg_regional_assessment_updated_at
    BEFORE UPDATE ON regional_assessment
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE regional_assessment IS 'Master regional readiness assessment with composite scoring';

-- ============================================================
-- 4. regional_dimension_score -- per-dimension detail
-- ============================================================
CREATE TABLE IF NOT EXISTS regional_dimension_score (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id UUID NOT NULL REFERENCES regional_assessment(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    dimension_key VARCHAR(50) NOT NULL,
    dimension_name VARCHAR(100) NOT NULL,
    weight NUMERIC(4,3) NOT NULL,
    raw_score NUMERIC(5,2) CHECK (raw_score >= 0 AND raw_score <= 100),
    normalized_score NUMERIC(5,2) CHECK (normalized_score >= 0 AND normalized_score <= 100),
    evidence_maturity_level INTEGER DEFAULT 1 CHECK (evidence_maturity_level >= 1 AND evidence_maturity_level <= 6),
    factors JSONB DEFAULT '{}',
    evidence_summary TEXT,
    uncertainty_notes TEXT,
    status VARCHAR(50) DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected')),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rds_assessment ON regional_dimension_score(assessment_id);
CREATE INDEX IF NOT EXISTS idx_rds_location ON regional_dimension_score(location_id);
CREATE INDEX IF NOT EXISTS idx_rds_dimension ON regional_dimension_score(dimension_key);

DROP TRIGGER IF EXISTS trg_regional_dimension_score_updated_at ON regional_dimension_score;
CREATE TRIGGER trg_regional_dimension_score_updated_at
    BEFORE UPDATE ON regional_dimension_score
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE regional_dimension_score IS 'Per-dimension readiness scores with evidence tracking';

-- ============================================================
-- 5. regional_benchmark -- external/internal benchmarks
-- ============================================================
CREATE TABLE IF NOT EXISTS regional_benchmark (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dimension_key VARCHAR(50) NOT NULL,
    benchmark_name VARCHAR(200) NOT NULL,
    benchmark_score NUMERIC(5,2) NOT NULL CHECK (benchmark_score >= 0 AND benchmark_score <= 100),
    benchmark_type VARCHAR(30) DEFAULT 'regional_average'
        CHECK (benchmark_type IN ('regional_average', 'best_practice', 'target', 'portfolio_average', 'custom')),
    source TEXT,
    methodology TEXT,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'active'
        CHECK (status IN ('active', 'deprecated')),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rb_dimension ON regional_benchmark(dimension_key);
CREATE INDEX IF NOT EXISTS idx_rb_type ON regional_benchmark(benchmark_type);

DROP TRIGGER IF EXISTS trg_regional_benchmark_updated_at ON regional_benchmark;
CREATE TRIGGER trg_regional_benchmark_updated_at
    BEFORE UPDATE ON regional_benchmark
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE regional_benchmark IS 'Benchmarks for regional readiness dimension scoring';

-- ============================================================
-- 6. v_regional_composite -- latest assessment per location
-- ============================================================
CREATE OR REPLACE VIEW v_regional_composite AS
SELECT DISTINCT ON (ra.location_id)
    ra.id AS assessment_id,
    ra.location_id,
    l.name AS location_name,
    ra.title,
    ra.period_start,
    ra.period_end,
    ra.composite_score,
    ra.rating,
    ra.confidence_level,
    ra.infrastructure_score,
    ra.institutions_score,
    ra.market_access_score,
    ra.natural_capital_score,
    ra.policy_environment_score,
    ra.human_capital_score,
    ra.evidence_summary,
    ra.uncertainty_notes,
    ra.status,
    ra.created_at,
    ra.updated_at
FROM regional_assessment ra
LEFT JOIN location l ON l.id = ra.location_id
WHERE ra.status IN ('verified', 'published')
ORDER BY ra.location_id, ra.created_at DESC;

-- ============================================================
-- 7. v_regional_dimension_detail -- all dimension scores
-- ============================================================
CREATE OR REPLACE VIEW v_regional_dimension_detail AS
SELECT
    rds.id AS score_id,
    rds.assessment_id,
    rds.location_id,
    l.name AS location_name,
    rds.dimension_key,
    rds.dimension_name,
    rds.weight,
    rds.raw_score,
    rds.normalized_score,
    rds.evidence_maturity_level,
    rds.factors,
    rds.evidence_summary,
    rds.uncertainty_notes,
    rds.status,
    ra.rating AS assessment_rating,
    ra.composite_score AS assessment_composite
FROM regional_dimension_score rds
LEFT JOIN regional_assessment ra ON ra.id = rds.assessment_id
LEFT JOIN location l ON l.id = rds.location_id
WHERE rds.status IN ('verified', 'published');

-- ============================================================
-- 8. v_regional_benchmark_compare -- assessment vs benchmark
-- ============================================================
CREATE OR REPLACE VIEW v_regional_benchmark_compare AS
SELECT
    rds.dimension_key,
    rds.dimension_name,
    rds.location_id,
    l.name AS location_name,
    rds.normalized_score AS assessment_score,
    rb.benchmark_name,
    rb.benchmark_score,
    rb.benchmark_type,
    ROUND(rds.normalized_score - rb.benchmark_score, 2) AS deviation,
    CASE
        WHEN rds.normalized_score >= rb.benchmark_score THEN 'above'
        WHEN rds.normalized_score >= rb.benchmark_score * 0.9 THEN 'near'
        ELSE 'below'
    END AS relative_position
FROM regional_dimension_score rds
JOIN regional_benchmark rb ON rb.dimension_key = rds.dimension_key AND rb.status = 'active'
LEFT JOIN location l ON l.id = rds.location_id
WHERE rds.status IN ('verified', 'published');

-- ============================================================
-- Seed default dimensions
-- ============================================================
INSERT INTO readiness_dimension (dimension_key, dimension_name, description, default_weight, data_sources, scoring_methodology)
VALUES
    ('infrastructure', 'Infrastructure', 'Power access, connectivity, transport proximity, equipment availability', 0.20,
     ARRAY['location', 'equipment_asset', 'sensor_registry', 'device_health'],
     'Weighted count of available infrastructure assets normalized to 0-100'),
    ('institutions', 'Institutions', 'Cooperative strength, partner engagement, governance maturity', 0.20,
     ARRAY['cooperative', 'partner', 'partner_lifecycle', 'stakeholder_feedback'],
     'Composite of partner engagement scores and cooperative membership'),
    ('market_access', 'Market Access', 'Demand density, price stability, channel diversity', 0.20,
     ARRAY['buyer_demand_signal', 'market_listing', 'market_price_observation', 'demand_forecast'],
     'Number of active channels weighted by demand volume'),
    ('natural_capital', 'Natural Capital', 'Soil health, carbon stocks, climate suitability, biodiversity', 0.20,
     ARRAY['tree_inventory', 'soil_carbon_measurement', 'weather_observation', 'biodiversity_metric'],
     'Composite of soil carbon, tree cover, and biodiversity indicators'),
    ('policy_environment', 'Policy Environment', 'Policy stability, certification access, regulatory clarity', 0.10,
     ARRAY['threat', 'threatcasting_signal', 'organic_certification_record'],
     'Inverse of policy risk count weighted by severity'),
    ('human_capital', 'Human Capital', 'Training coverage, skill levels, community engagement', 0.10,
     ARRAY['training_event', 'stakeholder_feedback', 'farm_worker'],
     'Training hours per worker weighted by skill assessment')
ON CONFLICT (dimension_key) DO UPDATE SET
    dimension_name = EXCLUDED.dimension_name,
    description = EXCLUDED.description,
    default_weight = EXCLUDED.default_weight,
    data_sources = EXCLUDED.data_sources,
    scoring_methodology = EXCLUDED.scoring_methodology;

COMMIT;
