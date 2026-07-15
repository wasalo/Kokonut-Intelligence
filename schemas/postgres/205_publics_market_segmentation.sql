-- Migration 205: Publics & Market Segmentation
--
-- Tables:
--   stakeholder_public  -- Formal stakeholder group classification
--   market_segment      -- Buyer segments by type
--
-- Views:
--   v_publics_matrix        -- Influence/interest grid
--   v_market_segment_summary -- Aggregated demand per segment

BEGIN;

-- ============================================================
-- 1. stakeholder_public -- formal stakeholder classification
-- ============================================================
CREATE TABLE IF NOT EXISTS stakeholder_public (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    public_type VARCHAR(30) NOT NULL
        CHECK (public_type IN ('financial', 'media', 'government', 'citizen_action',
                               'local_community', 'general_public', 'employees',
                               'academic', 'industry')),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    influence_score NUMERIC(3,1) DEFAULT 5.0 CHECK (influence_score >= 1.0 AND influence_score <= 10.0),
    interest_score NUMERIC(3,1) DEFAULT 5.0 CHECK (interest_score >= 1.0 AND interest_score <= 10.0),
    stance VARCHAR(20) DEFAULT 'neutral'
        CHECK (stance IN ('supportive', 'neutral', 'opposed')),
    stance_notes TEXT,
    contact_info JSONB DEFAULT '{}',
    evidence_source JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected')),
    created_by UUID,
    updated_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sp_location ON stakeholder_public(location_id);
CREATE INDEX IF NOT EXISTS idx_sp_type ON stakeholder_public(public_type);
CREATE INDEX IF NOT EXISTS idx_sp_stance ON stakeholder_public(stance);

DROP TRIGGER IF EXISTS trg_stakeholder_public_updated_at ON stakeholder_public;
CREATE TRIGGER trg_stakeholder_public_updated_at
    BEFORE UPDATE ON stakeholder_public
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE stakeholder_public IS 'Formal stakeholder group classification with influence/interest scoring';

-- ============================================================
-- 2. market_segment -- buyer segments by type
-- ============================================================
CREATE TABLE IF NOT EXISTS market_segment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    segment_type VARCHAR(30) NOT NULL
        CHECK (segment_type IN ('consumer', 'business', 'government', 'export', 'reseller')),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    demand_pattern VARCHAR(50),
    pricing_range JSONB DEFAULT '{}',
    channel_preferences JSONB DEFAULT '[]',
    size_estimate NUMERIC(12,2),
    size_unit VARCHAR(20),
    active_demand_count INTEGER DEFAULT 0,
    avg_price NUMERIC(10,2),
    evidence_source JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected')),
    created_by UUID,
    updated_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ms_location ON market_segment(location_id);
CREATE INDEX IF NOT EXISTS idx_ms_type ON market_segment(segment_type);

DROP TRIGGER IF EXISTS trg_market_segment_updated_at ON market_segment;
CREATE TRIGGER trg_market_segment_updated_at
    BEFORE UPDATE ON market_segment
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE market_segment IS 'Buyer segments by type with demand patterns and pricing';

-- ============================================================
-- 3. v_publics_matrix -- influence/interest grid
-- ============================================================
CREATE OR REPLACE VIEW v_publics_matrix AS
SELECT
    sp.id,
    sp.location_id,
    l.name AS location_name,
    sp.public_type,
    sp.name,
    sp.influence_score,
    sp.interest_score,
    sp.stance,
    CASE
        WHEN sp.influence_score >= 7 AND sp.interest_score >= 7 THEN 'key_player'
        WHEN sp.influence_score >= 7 AND sp.interest_score < 7 THEN 'keep_satisfied'
        WHEN sp.influence_score < 7 AND sp.interest_score >= 7 THEN 'keep_informed'
        ELSE 'monitor'
    END AS quadrant,
    sp.status,
    sp.created_at
FROM stakeholder_public sp
LEFT JOIN location l ON l.id = sp.location_id
WHERE sp.status IN ('verified', 'published')
ORDER BY sp.influence_score DESC, sp.interest_score DESC;

-- ============================================================
-- 4. v_market_segment_summary -- aggregated demand per segment
-- ============================================================
CREATE OR REPLACE VIEW v_market_segment_summary AS
SELECT
    ms.id AS segment_id,
    ms.location_id,
    l.name AS location_name,
    ms.segment_type,
    ms.name AS segment_name,
    ms.size_estimate,
    ms.size_unit,
    ms.avg_price,
    ms.active_demand_count,
    ms.demand_pattern,
    ms.status,
    ms.created_at
FROM market_segment ms
LEFT JOIN location l ON l.id = ms.location_id
WHERE ms.status IN ('verified', 'published')
ORDER BY ms.segment_type, ms.size_estimate DESC NULLS LAST;

COMMIT;
