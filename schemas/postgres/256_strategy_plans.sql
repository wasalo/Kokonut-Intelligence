-- ============================================================
-- 256_strategy_plans.sql
-- Versioned strategy kernel for organization and location scopes.
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy_plan (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_type VARCHAR(20) NOT NULL CHECK (scope_type IN ('organization', 'location')),
    scope_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    planning_horizon_start DATE NOT NULL,
    planning_horizon_end DATE NOT NULL,
    diagnosis_summary TEXT NOT NULL DEFAULT '',
    guiding_policy TEXT NOT NULL DEFAULT '',
    theory_of_change TEXT,
    uncertainty_summary TEXT,
    approval_mode VARCHAR(30) NOT NULL DEFAULT 'governance_circle'
        CHECK (approval_mode IN ('governance_circle', 'stakeholder_decision', 'dual')),
    visibility VARCHAR(20) NOT NULL DEFAULT 'private'
        CHECK (visibility IN ('private', 'limited', 'public')),
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'approved', 'active', 'superseded', 'retired')),
    supersedes_plan_id UUID REFERENCES strategy_plan(id) ON DELETE SET NULL,
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    review_due_at DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (planning_horizon_end >= planning_horizon_start),
    CHECK (status NOT IN ('approved', 'active') OR NULLIF(BTRIM(diagnosis_summary), '') IS NOT NULL),
    CHECK (status NOT IN ('approved', 'active') OR NULLIF(BTRIM(guiding_policy), '') IS NOT NULL),
    CHECK (status NOT IN ('approved', 'active') OR approved_by_party_id IS NOT NULL),
    CHECK (status NOT IN ('approved', 'active') OR approved_at IS NOT NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_strategy_plan_scope_version
    ON strategy_plan(scope_type, scope_id, version);
CREATE UNIQUE INDEX IF NOT EXISTS uq_strategy_plan_active_scope
    ON strategy_plan(scope_type, scope_id)
    WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_strategy_plan_scope_status
    ON strategy_plan(scope_type, scope_id, status, planning_horizon_end);

ALTER TABLE strategy_map
    ADD COLUMN IF NOT EXISTS strategy_plan_id UUID REFERENCES strategy_plan(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS accountable_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS leading_or_lagging VARCHAR(10) NOT NULL DEFAULT 'lagging'
        CHECK (leading_or_lagging IN ('leading', 'lagging')),
    ADD COLUMN IF NOT EXISTS review_cadence VARCHAR(30),
    ADD COLUMN IF NOT EXISTS visibility VARCHAR(20) NOT NULL DEFAULT 'private'
        CHECK (visibility IN ('private', 'limited', 'public'));

CREATE INDEX IF NOT EXISTS idx_strategy_map_plan
    ON strategy_map(strategy_plan_id, status);
CREATE INDEX IF NOT EXISTS idx_strategy_map_accountable
    ON strategy_map(accountable_party_id, status);

DROP TRIGGER IF EXISTS trg_strategy_plan_updated_at ON strategy_plan;
CREATE TRIGGER trg_strategy_plan_updated_at BEFORE UPDATE ON strategy_plan
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE strategy_plan IS 'Immutable-versioned strategy kernel scoped to an organization or location';
COMMENT ON COLUMN strategy_plan.approval_mode IS 'Approval route selected by scope: governance circle, stakeholder decision, or both';
COMMENT ON COLUMN strategy_plan.visibility IS 'Private by default; publication requires governed approval';
