-- ============================================================
-- 212_technology_roadmap.sql - Governed technology roadmapping
-- ============================================================
-- Connects enterprise needs and capability gaps to technology choices,
-- delivery initiatives, and periodic human review.

CREATE TABLE IF NOT EXISTS technology_roadmap (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    entity_type VARCHAR(30) NOT NULL DEFAULT 'platform'
        CHECK (entity_type IN ('platform', 'organization', 'location')),
    entity_id UUID,
    planning_horizon_start DATE,
    planning_horizon_end DATE,
    detail_level VARCHAR(20) NOT NULL DEFAULT 'portfolio'
        CHECK (detail_level IN ('executive', 'portfolio', 'delivery')),
    sponsor VARCHAR(120),
    owner VARCHAR(120),
    review_cadence_days INTEGER CHECK (review_cadence_days > 0),
    next_review_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'approved', 'active', 'reviewed', 'superseded', 'rejected')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tr_entity ON technology_roadmap(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_tr_status ON technology_roadmap(status);
CREATE INDEX IF NOT EXISTS idx_tr_review ON technology_roadmap(next_review_at);

DROP TRIGGER IF EXISTS trg_tr_updated_at ON technology_roadmap;
CREATE TRIGGER trg_tr_updated_at
    BEFORE UPDATE ON technology_roadmap
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS technology_roadmap_requirement (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    roadmap_id UUID NOT NULL REFERENCES technology_roadmap(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    need_type VARCHAR(30) NOT NULL DEFAULT 'business'
        CHECK (need_type IN ('business', 'customer', 'operational', 'regulatory', 'sustainability')),
    priority SMALLINT NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    target_value NUMERIC,
    unit VARCHAR(40),
    target_date DATE,
    strategy_map_id UUID REFERENCES strategy_map(id) ON DELETE SET NULL,
    capability_id UUID REFERENCES business_capability(id) ON DELETE SET NULL,
    value_stream_id UUID REFERENCES value_stream_definition(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'validated', 'in_progress', 'met', 'deferred', 'retired')),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trr_roadmap ON technology_roadmap_requirement(roadmap_id);
CREATE INDEX IF NOT EXISTS idx_trr_capability ON technology_roadmap_requirement(capability_id);
CREATE INDEX IF NOT EXISTS idx_trr_stream ON technology_roadmap_requirement(value_stream_id);

CREATE TABLE IF NOT EXISTS technology_area (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    roadmap_id UUID NOT NULL REFERENCES technology_roadmap(id) ON DELETE CASCADE,
    name VARCHAR(160) NOT NULL,
    description TEXT,
    sequence_order SMALLINT NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'deprecated')),
    UNIQUE (roadmap_id, name)
);

CREATE INDEX IF NOT EXISTS idx_ta_roadmap ON technology_area(roadmap_id);

CREATE TABLE IF NOT EXISTS technology_driver (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    area_id UUID NOT NULL REFERENCES technology_area(id) ON DELETE CASCADE,
    requirement_id UUID REFERENCES technology_roadmap_requirement(id) ON DELETE SET NULL,
    name VARCHAR(160) NOT NULL,
    metric_key VARCHAR(100),
    target_value NUMERIC,
    unit VARCHAR(40),
    target_date DATE,
    weight NUMERIC NOT NULL DEFAULT 1.0 CHECK (weight >= 0 AND weight <= 10),
    UNIQUE (area_id, name)
);

CREATE INDEX IF NOT EXISTS idx_td_area ON technology_driver(area_id);
CREATE INDEX IF NOT EXISTS idx_td_requirement ON technology_driver(requirement_id);

CREATE TABLE IF NOT EXISTS technology_alternative (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_id UUID NOT NULL REFERENCES technology_driver(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    maturity_status VARCHAR(20) NOT NULL DEFAULT 'candidate'
        CHECK (maturity_status IN ('emerging', 'available', 'pilot', 'production', 'deprecated')),
    expected_maturity_date DATE,
    estimated_cost NUMERIC,
    confidence NUMERIC CHECK (confidence >= 0 AND confidence <= 1),
    recommendation VARCHAR(20) NOT NULL DEFAULT 'candidate'
        CHECK (recommendation IN ('candidate', 'selected', 'rejected', 'deferred')),
    decision_rationale TEXT,
    transition_from_id UUID REFERENCES technology_alternative(id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (driver_id, name)
);

CREATE INDEX IF NOT EXISTS idx_talt_driver ON technology_alternative(driver_id);
CREATE INDEX IF NOT EXISTS idx_talt_recommendation ON technology_alternative(recommendation);

CREATE TABLE IF NOT EXISTS technology_roadmap_review (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    roadmap_id UUID NOT NULL REFERENCES technology_roadmap(id) ON DELETE CASCADE,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_by UUID,
    result VARCHAR(20) NOT NULL
        CHECK (result IN ('approved', 'needs_revision', 'rejected', 'superseded')),
    notes TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_trv_roadmap ON technology_roadmap_review(roadmap_id, reviewed_at DESC);

CREATE OR REPLACE VIEW v_technology_roadmap_overview AS
SELECT
    tr.id AS roadmap_id,
    tr.name,
    tr.entity_type,
    tr.entity_id,
    tr.planning_horizon_start,
    tr.planning_horizon_end,
    tr.detail_level,
    tr.sponsor,
    tr.owner,
    tr.status,
    tr.next_review_at,
    COUNT(DISTINCT req.id) AS requirement_count,
    COUNT(DISTINCT ta.id) AS technology_area_count,
    COUNT(DISTINCT td.id) AS driver_count,
    COUNT(DISTINCT alt.id) AS alternative_count,
    COUNT(DISTINCT alt.id) FILTER (WHERE alt.recommendation = 'selected') AS selected_alternative_count,
    MAX(rv.reviewed_at) AS last_reviewed_at
FROM technology_roadmap tr
LEFT JOIN technology_roadmap_requirement req ON req.roadmap_id = tr.id
LEFT JOIN technology_area ta ON ta.roadmap_id = tr.id
LEFT JOIN technology_driver td ON td.area_id = ta.id
LEFT JOIN technology_alternative alt ON alt.driver_id = td.id
LEFT JOIN technology_roadmap_review rv ON rv.roadmap_id = tr.id
GROUP BY tr.id;

COMMENT ON TABLE technology_roadmap IS 'Governed enterprise technology roadmap anchored to needs, capabilities, and review decisions';
COMMENT ON TABLE technology_roadmap_requirement IS 'Business and system needs that technology investments must satisfy';
COMMENT ON TABLE technology_area IS 'Major technology areas used to satisfy roadmap requirements';
COMMENT ON TABLE technology_driver IS 'Measurable technology selection criteria and targets';
COMMENT ON TABLE technology_alternative IS 'Technology options, maturity timelines, trade-offs, and recommendations';
COMMENT ON TABLE technology_roadmap_review IS 'Human review history for roadmap validation and change control';
COMMENT ON VIEW v_technology_roadmap_overview IS 'Roadmap portfolio counts and review status';
