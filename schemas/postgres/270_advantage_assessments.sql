-- ============================================================
-- 270_advantage_assessments.sql
-- VRIO-style defensible advantage assessment.
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy_advantage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    position_id UUID REFERENCES strategy_position(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    statement TEXT NOT NULL,
    valuable_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (valuable_score BETWEEN 0 AND 100),
    rare_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (rare_score BETWEEN 0 AND 100),
    inimitable_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (inimitable_score BETWEEN 0 AND 100),
    organized_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (organized_score BETWEEN 0 AND 100),
    switching_cost_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (switching_cost_score BETWEEN 0 AND 100),
    network_effect_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (network_effect_score BETWEEN 0 AND 100),
    evidence_advantage_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (evidence_advantage_score BETWEEN 0 AND 100),
    ecological_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (ecological_score BETWEEN 0 AND 100),
    social_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (social_score BETWEEN 0 AND 100),
    governance_trust_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (governance_trust_score BETWEEN 0 AND 100),
    defensibility_score NUMERIC(6,2),
    imitation_risk VARCHAR(20) NOT NULL DEFAULT 'unknown' CHECK (imitation_risk IN ('low', 'medium', 'high', 'unknown')),
    capture_risk VARCHAR(20) NOT NULL DEFAULT 'unknown' CHECK (capture_risk IN ('low', 'medium', 'high', 'unknown')),
    evidence JSONB NOT NULL DEFAULT '[]',
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'superseded')),
    owner_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    assessed_at TIMESTAMPTZ,
    assessed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_advantage_plan ON strategy_advantage(strategy_plan_id, status, defensibility_score DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_advantage_position ON strategy_advantage(position_id, status);
CREATE INDEX IF NOT EXISTS idx_strategy_advantage_risk ON strategy_advantage(imitation_risk, capture_risk, status);

DROP TRIGGER IF EXISTS trg_strategy_advantage_updated_at ON strategy_advantage;
CREATE TRIGGER trg_strategy_advantage_updated_at BEFORE UPDATE ON strategy_advantage
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE strategy_advantage IS 'VRIO-style defensible advantage with trust, network, evidence, ecological, and social dimensions';
