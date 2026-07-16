-- ============================================================
-- 257_strategy_choices_assumptions.sql
-- Explicit choices, alternatives, trade-offs, and assumptions.
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy_choice (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    choice_type VARCHAR(30) NOT NULL CHECK (choice_type IN ('where_to_play', 'how_to_win', 'not_to_do', 'position', 'policy', 'operating_model')),
    statement TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    stakeholder_impact TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'approved', 'rejected', 'superseded')),
    visibility VARCHAR(20) NOT NULL DEFAULT 'private'
        CHECK (visibility IN ('private', 'limited', 'public')),
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status NOT IN ('approved', 'superseded') OR approved_by_party_id IS NOT NULL),
    CHECK (status NOT IN ('approved', 'superseded') OR approved_at IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS strategy_alternative (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    choice_id UUID NOT NULL REFERENCES strategy_choice(id) ON DELETE CASCADE,
    statement TEXT NOT NULL,
    expected_outcome TEXT,
    reason_not_selected TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'considered'
        CHECK (status IN ('considered', 'rejected', 'selected', 'deferred')),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategy_tradeoff (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    choice_id UUID NOT NULL REFERENCES strategy_choice(id) ON DELETE CASCADE,
    favored_dimension VARCHAR(100) NOT NULL,
    constrained_dimension VARCHAR(100) NOT NULL,
    rationale TEXT NOT NULL,
    affected_stakeholders JSONB NOT NULL DEFAULT '[]'::jsonb,
    mitigation TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategy_assumption (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    statement TEXT NOT NULL,
    confidence NUMERIC(5,4) NOT NULL DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    importance VARCHAR(20) NOT NULL DEFAULT 'medium'
        CHECK (importance IN ('low', 'medium', 'high', 'critical')),
    test_metric_key VARCHAR(120),
    trigger_operator VARCHAR(10) CHECK (trigger_operator IN ('gte', 'lte', 'eq', 'neq', 'between')),
    trigger_threshold NUMERIC,
    owner_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'untested'
        CHECK (status IN ('untested', 'testing', 'validated', 'invalidated', 'retired')),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    last_tested_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_choice_plan ON strategy_choice(strategy_plan_id, status);
CREATE INDEX IF NOT EXISTS idx_strategy_alternative_choice ON strategy_alternative(choice_id, status);
CREATE INDEX IF NOT EXISTS idx_strategy_tradeoff_choice ON strategy_tradeoff(choice_id);
CREATE INDEX IF NOT EXISTS idx_strategy_assumption_plan ON strategy_assumption(strategy_plan_id, status, importance);
CREATE INDEX IF NOT EXISTS idx_strategy_assumption_metric ON strategy_assumption(test_metric_key, status);

DROP TRIGGER IF EXISTS trg_strategy_choice_updated_at ON strategy_choice;
CREATE TRIGGER trg_strategy_choice_updated_at BEFORE UPDATE ON strategy_choice
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_strategy_assumption_updated_at ON strategy_assumption;
CREATE TRIGGER trg_strategy_assumption_updated_at BEFORE UPDATE ON strategy_assumption
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE strategy_choice IS 'Private-by-default strategic choices and policies within a versioned strategy plan';
COMMENT ON TABLE strategy_alternative IS 'Considered, rejected, deferred, and selected alternatives preserving strategic reasoning';
COMMENT ON TABLE strategy_tradeoff IS 'Explicit dimension trade-offs and stakeholder mitigations for a strategic choice';
COMMENT ON TABLE strategy_assumption IS 'Testable assumptions with metrics, thresholds, owners, and validation state';
