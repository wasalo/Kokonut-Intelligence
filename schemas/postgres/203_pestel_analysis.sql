-- Migration 203: PESTEL Analysis
--
-- Tables:
--   pestel_analysis  -- Macro-environment assessment per location+period
--   pestel_factor    -- Individual PESTEL factors within an analysis
--
-- Views:
--   v_pestel_summary       -- Aggregated scores per category
--   v_pestel_high_impact   -- Factors with impact >= 7

BEGIN;

-- ============================================================
-- 1. pestel_analysis -- macro-environment assessment
-- ============================================================
CREATE TABLE IF NOT EXISTS pestel_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    status VARCHAR(50) DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected')),
    political_score NUMERIC(5,2) DEFAULT 0 CHECK (political_score >= 0 AND political_score <= 10),
    economic_score NUMERIC(5,2) DEFAULT 0 CHECK (economic_score >= 0 AND economic_score <= 10),
    social_score NUMERIC(5,2) DEFAULT 0 CHECK (social_score >= 0 AND social_score <= 10),
    technological_score NUMERIC(5,2) DEFAULT 0 CHECK (technological_score >= 0 AND technological_score <= 10),
    environmental_score NUMERIC(5,2) DEFAULT 0 CHECK (environmental_score >= 0 AND environmental_score <= 10),
    legal_score NUMERIC(5,2) DEFAULT 0 CHECK (legal_score >= 0 AND legal_score <= 10),
    overall_score NUMERIC(5,2) DEFAULT 0 CHECK (overall_score >= 0 AND overall_score <= 10),
    factor_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_by UUID,
    updated_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pa_location ON pestel_analysis(location_id);
CREATE INDEX IF NOT EXISTS idx_pa_status ON pestel_analysis(status);
CREATE INDEX IF NOT EXISTS idx_pa_period ON pestel_analysis(period_start, period_end);

DROP TRIGGER IF EXISTS trg_pestel_analysis_updated_at ON pestel_analysis;
CREATE TRIGGER trg_pestel_analysis_updated_at
    BEFORE UPDATE ON pestel_analysis
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE pestel_analysis IS 'Macro-environment PESTEL assessment per location and period';

-- ============================================================
-- 2. pestel_factor -- individual PESTEL factors
-- ============================================================
CREATE TABLE IF NOT EXISTS pestel_factor (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    analysis_id UUID NOT NULL REFERENCES pestel_analysis(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    category VARCHAR(20) NOT NULL
        CHECK (category IN ('political', 'economic', 'social', 'technological', 'environmental', 'legal')),
    factor_type VARCHAR(20) NOT NULL
        CHECK (factor_type IN ('strength', 'opportunity', 'risk', 'neutral')),
    title VARCHAR(200) NOT NULL,
    description TEXT,
    impact_score NUMERIC(3,1) NOT NULL DEFAULT 5.0 CHECK (impact_score >= 1.0 AND impact_score <= 10.0),
    likelihood NUMERIC(3,2) DEFAULT 0.5 CHECK (likelihood >= 0.0 AND likelihood <= 1.0),
    evidence_source JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected')),
    created_by UUID,
    updated_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pf_analysis ON pestel_factor(analysis_id);
CREATE INDEX IF NOT EXISTS idx_pf_location ON pestel_factor(location_id);
CREATE INDEX IF NOT EXISTS idx_pf_category ON pestel_factor(category);
CREATE INDEX IF NOT EXISTS idx_pf_type ON pestel_factor(factor_type);

DROP TRIGGER IF EXISTS trg_pestel_factor_updated_at ON pestel_factor;
CREATE TRIGGER trg_pestel_factor_updated_at
    BEFORE UPDATE ON pestel_factor
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE pestel_factor IS 'Individual PESTEL factors with impact and likelihood scoring';

-- ============================================================
-- 3. v_pestel_summary -- aggregated scores per category
-- ============================================================
CREATE OR REPLACE VIEW v_pestel_summary AS
SELECT
    a.id AS analysis_id,
    a.location_id,
    l.name AS location_name,
    a.title,
    a.period_start,
    a.period_end,
    a.political_score,
    a.economic_score,
    a.social_score,
    a.technological_score,
    a.environmental_score,
    a.legal_score,
    a.overall_score,
    a.factor_count,
    a.status,
    COUNT(CASE WHEN f.category = 'political' THEN 1 END) AS political_factors,
    COUNT(CASE WHEN f.category = 'economic' THEN 1 END) AS economic_factors,
    COUNT(CASE WHEN f.category = 'social' THEN 1 END) AS social_factors,
    COUNT(CASE WHEN f.category = 'technological' THEN 1 END) AS technological_factors,
    COUNT(CASE WHEN f.category = 'environmental' THEN 1 END) AS environmental_factors,
    COUNT(CASE WHEN f.category = 'legal' THEN 1 END) AS legal_factors,
    a.created_at,
    a.updated_at
FROM pestel_analysis a
LEFT JOIN location l ON l.id = a.location_id
LEFT JOIN pestel_factor f ON f.analysis_id = a.id
GROUP BY a.id, l.name;

-- ============================================================
-- 4. v_pestel_high_impact -- factors with impact >= 7
-- ============================================================
CREATE OR REPLACE VIEW v_pestel_high_impact AS
SELECT
    f.id AS factor_id,
    f.analysis_id,
    f.location_id,
    l.name AS location_name,
    f.category,
    f.factor_type,
    f.title,
    f.description,
    f.impact_score,
    f.likelihood,
    f.evidence_source,
    f.status,
    a.title AS analysis_title,
    a.period_start,
    a.period_end
FROM pestel_factor f
JOIN pestel_analysis a ON a.id = f.analysis_id
LEFT JOIN location l ON l.id = f.location_id
WHERE f.impact_score >= 7.0
    AND f.status IN ('verified', 'published')
ORDER BY f.impact_score DESC;

COMMIT;
