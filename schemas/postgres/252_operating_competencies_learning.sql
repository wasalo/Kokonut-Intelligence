-- ============================================================
-- 252_operating_competencies_learning.sql
-- Role capability evidence and development plans.
-- ============================================================

CREATE TABLE IF NOT EXISTS operating_competency_profile (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    governance_role_id UUID REFERENCES governance_role(id) ON DELETE CASCADE,
    competency_key VARCHAR(120) NOT NULL,
    current_level NUMERIC(4,2) NOT NULL DEFAULT 0 CHECK (current_level >= 0 AND current_level <= 5),
    target_level NUMERIC(4,2) NOT NULL DEFAULT 3 CHECK (target_level >= 0 AND target_level <= 5),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    assessed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    assessed_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'superseded')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (party_id, governance_role_id, competency_key),
    CHECK (target_level >= current_level OR status IN ('draft', 'superseded'))
);

CREATE INDEX IF NOT EXISTS idx_operating_competency_party
    ON operating_competency_profile(party_id, status);
CREATE INDEX IF NOT EXISTS idx_operating_competency_gap
    ON operating_competency_profile(governance_role_id, competency_key, status)
    WHERE target_level > current_level;

CREATE TABLE IF NOT EXISTS operating_learning_plan (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    scope_type VARCHAR(20) NOT NULL CHECK (scope_type IN ('internal', 'adelphi')),
    scope_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    competency_goals JSONB NOT NULL DEFAULT '[]'::jsonb,
    support_requested JSONB NOT NULL DEFAULT '[]'::jsonb,
    target_date DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'active', 'completed', 'paused', 'cancelled')),
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_operating_learning_plan_party
    ON operating_learning_plan(party_id, status);
CREATE INDEX IF NOT EXISTS idx_operating_learning_plan_scope
    ON operating_learning_plan(scope_type, scope_id, status);

CREATE OR REPLACE VIEW v_operating_competency_gaps AS
SELECT id, party_id, governance_role_id, competency_key,
       current_level, target_level, target_level - current_level AS gap_level,
       evidence, status
FROM operating_competency_profile
WHERE status IN ('submitted', 'verified') AND target_level > current_level;

DROP TRIGGER IF EXISTS trg_operating_competency_updated_at ON operating_competency_profile;
CREATE TRIGGER trg_operating_competency_updated_at BEFORE UPDATE ON operating_competency_profile
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_operating_learning_plan_updated_at ON operating_learning_plan;
CREATE TRIGGER trg_operating_learning_plan_updated_at BEFORE UPDATE ON operating_learning_plan
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
