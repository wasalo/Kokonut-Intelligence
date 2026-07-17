-- ============================================================
-- 309_relationship_entities.sql
-- First-class entities for high-value relationship-shaped fields.
-- ============================================================

CREATE TABLE IF NOT EXISTS farmer_crop (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farmer_id UUID NOT NULL REFERENCES farmer_profile(id) ON DELETE CASCADE,
    crop_id UUID NOT NULL REFERENCES crop(id) ON DELETE RESTRICT,
    season_key VARCHAR(80),
    role VARCHAR(20) NOT NULL DEFAULT 'primary'
        CHECK (role IN ('primary', 'secondary', 'trial', 'historical')),
    area_ha NUMERIC(12,4) CHECK (area_ha IS NULL OR area_ha >= 0),
    valid_from DATE,
    valid_until DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('planned', 'active', 'ended', 'rejected')),
    source_ref TEXT,
    evidence_maturity INTEGER REFERENCES evidence_maturity_level(level),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from),
    UNIQUE (farmer_id, crop_id, season_key)
);

CREATE INDEX IF NOT EXISTS idx_farmer_crop_farmer_status
    ON farmer_crop(farmer_id, status);
CREATE INDEX IF NOT EXISTS idx_farmer_crop_crop
    ON farmer_crop(crop_id, status);

CREATE TABLE IF NOT EXISTS metric_value_source (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_value_id UUID NOT NULL REFERENCES metric_value(id) ON DELETE CASCADE,
    source_entity_type VARCHAR(80) NOT NULL,
    source_entity_id UUID,
    source_ref TEXT,
    contribution_role VARCHAR(30) NOT NULL DEFAULT 'supporting'
        CHECK (contribution_role IN ('primary', 'supporting', 'exclusion', 'context')),
    sequence_order INTEGER NOT NULL DEFAULT 1 CHECK (sequence_order > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (metric_value_id, source_entity_type, source_entity_id, source_ref)
);

CREATE INDEX IF NOT EXISTS idx_metric_value_source_value
    ON metric_value_source(metric_value_id, sequence_order);
CREATE INDEX IF NOT EXISTS idx_metric_value_source_entity
    ON metric_value_source(source_entity_type, source_entity_id);

CREATE TABLE IF NOT EXISTS cooperative_board_member (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cooperative_id UUID NOT NULL REFERENCES cooperative(id) ON DELETE CASCADE,
    membership_id UUID NOT NULL REFERENCES cooperative_membership(id) ON DELETE RESTRICT,
    board_role VARCHAR(80) NOT NULL DEFAULT 'director',
    term_start DATE NOT NULL,
    term_end DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('nominated', 'active', 'ended', 'removed')),
    source_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (term_end IS NULL OR term_end >= term_start),
    UNIQUE (cooperative_id, membership_id, term_start)
);

CREATE INDEX IF NOT EXISTS idx_coop_board_current
    ON cooperative_board_member(cooperative_id, status, term_start DESC);

CREATE TABLE IF NOT EXISTS forecast_assumption (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_id UUID NOT NULL REFERENCES forecast_scenario(id) ON DELETE CASCADE,
    assumption_key VARCHAR(120) NOT NULL,
    value JSONB NOT NULL,
    unit VARCHAR(80),
    source_type VARCHAR(80),
    source_ref TEXT,
    sequence_order INTEGER NOT NULL DEFAULT 1 CHECK (sequence_order > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (scenario_id, assumption_key, sequence_order)
);

CREATE INDEX IF NOT EXISTS idx_forecast_assumption_scenario
    ON forecast_assumption(scenario_id, assumption_key);

CREATE TABLE IF NOT EXISTS role_permission (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_assignment_id UUID NOT NULL REFERENCES role_assignment(id) ON DELETE CASCADE,
    resource VARCHAR(120) NOT NULL,
    action VARCHAR(80) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'revoked')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (role_assignment_id, resource, action)
);

CREATE INDEX IF NOT EXISTS idx_role_permission_assignment
    ON role_permission(role_assignment_id, status);

COMMENT ON TABLE farmer_crop IS 'Explicit farmer-to-crop relationship replacing relationship-shaped crop arrays over time';
COMMENT ON TABLE metric_value_source IS 'Ordered metric provenance links replacing UUID arrays';
COMMENT ON TABLE cooperative_board_member IS 'Governed cooperative board membership with term semantics';
COMMENT ON TABLE forecast_assumption IS 'Versionable forecast assumptions replacing opaque assumption JSON fields';
COMMENT ON TABLE role_permission IS 'Explicit role permissions replacing embedded permission arrays';
