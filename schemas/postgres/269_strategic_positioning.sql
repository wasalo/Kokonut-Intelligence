-- ============================================================
-- 269_strategic_positioning.sql
-- Target positions and segment-specific value propositions.
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy_position (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    landscape_id UUID REFERENCES competitive_landscape(id) ON DELETE SET NULL,
    target_type VARCHAR(30) NOT NULL CHECK (target_type IN ('market_segment', 'stakeholder_public', 'party', 'geography', 'industry', 'network')),
    target_id UUID,
    target_name VARCHAR(255) NOT NULL,
    customer_needs TEXT NOT NULL,
    value_drivers JSONB NOT NULL DEFAULT '[]',
    value_proposition TEXT NOT NULL,
    differentiation TEXT NOT NULL,
    alternatives JSONB NOT NULL DEFAULT '[]',
    excluded_scope TEXT,
    geographic_scope TEXT,
    product_service_scope TEXT,
    position_score NUMERIC(5,2) CHECK (position_score IS NULL OR position_score BETWEEN 0 AND 100),
    confidence VARCHAR(20) NOT NULL DEFAULT 'moderate' CHECK (confidence IN ('high', 'moderate', 'low', 'insufficient_evidence')),
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'approved', 'superseded')),
    visibility VARCHAR(20) NOT NULL DEFAULT 'private'
        CHECK (visibility IN ('private', 'limited', 'public')),
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status <> 'approved' OR approved_by_party_id IS NOT NULL),
    CHECK (status <> 'approved' OR approved_at IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_strategy_position_plan ON strategy_position(strategy_plan_id, status);
CREATE INDEX IF NOT EXISTS idx_strategy_position_landscape ON strategy_position(landscape_id, status);
CREATE INDEX IF NOT EXISTS idx_strategy_position_target ON strategy_position(target_type, target_id);

DROP TRIGGER IF EXISTS trg_strategy_position_updated_at ON strategy_position;
CREATE TRIGGER trg_strategy_position_updated_at BEFORE UPDATE ON strategy_position
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE strategy_position IS 'Private-by-default strategic position and value proposition for a target segment or stakeholder group';
