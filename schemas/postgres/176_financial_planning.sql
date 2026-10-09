-- ============================================================
-- 176_financial_planning.sql - Enterprise planning: budgeting (FP&A)
-- ============================================================

DO $$ BEGIN
    CREATE TYPE plan_status AS ENUM ('draft', 'approved', 'active', 'closed', 'cancelled');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- A financial plan links a strategic objective to a budget and a period.
-- Its lifecycle is governed by the budget workflow specification.
CREATE TABLE IF NOT EXISTS financial_plan (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    objective_id UUID REFERENCES objective(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    status plan_status NOT NULL DEFAULT 'draft',
    created_by_type VARCHAR(20) NOT NULL DEFAULT 'system'
        CHECK (created_by_type IN ('staff', 'farmer', 'agent', 'system')),
    created_by_id UUID,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT financial_plan_period_order CHECK (period_end >= period_start)
);

CREATE INDEX IF NOT EXISTS idx_financial_plan_org ON financial_plan(organization_id);
CREATE INDEX IF NOT EXISTS idx_financial_plan_objective ON financial_plan(objective_id);

-- Budget lines allocate planned spend by category and (optionally) location.
CREATE TABLE IF NOT EXISTS budget_line (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES financial_plan(id) ON DELETE CASCADE,
    category VARCHAR(100) NOT NULL,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    amount NUMERIC(15, 2) NOT NULL,
    notes TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_budget_line_plan ON budget_line(plan_id);
CREATE INDEX IF NOT EXISTS idx_budget_line_category ON budget_line(category);

-- Optional scenario variants of a plan for S&OP / what-if analysis.
CREATE TABLE IF NOT EXISTS planning_scenario (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES financial_plan(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    assumptions JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_planning_scenario_plan ON planning_scenario(plan_id);

DROP TRIGGER IF EXISTS trg_financial_plan_updated_at ON financial_plan;
CREATE TRIGGER trg_financial_plan_updated_at
    BEFORE UPDATE ON financial_plan
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_budget_line_updated_at ON budget_line;
CREATE TRIGGER trg_budget_line_updated_at
    BEFORE UPDATE ON budget_line
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_planning_scenario_updated_at ON planning_scenario;
CREATE TRIGGER trg_planning_scenario_updated_at
    BEFORE UPDATE ON planning_scenario
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE financial_plan IS 'Financial plan linking a strategic objective to a budget and period';
COMMENT ON TABLE budget_line IS 'Planned spend by category and location';
COMMENT ON TABLE planning_scenario IS 'Scenario variants of a financial plan';
