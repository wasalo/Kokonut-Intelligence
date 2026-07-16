-- ============================================================
-- 258_strategy_investments_allocation.sql
-- Composite strategic investment scoring and governed allocation.
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy_allocation_policy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL UNIQUE REFERENCES strategy_plan(id) ON DELETE CASCADE,
    financial_weight NUMERIC(6,5) NOT NULL DEFAULT 0.20 CHECK (financial_weight >= 0),
    ecological_weight NUMERIC(6,5) NOT NULL DEFAULT 0.20 CHECK (ecological_weight >= 0),
    social_weight NUMERIC(6,5) NOT NULL DEFAULT 0.20 CHECK (social_weight >= 0),
    governance_weight NUMERIC(6,5) NOT NULL DEFAULT 0.15 CHECK (governance_weight >= 0),
    resilience_weight NUMERIC(6,5) NOT NULL DEFAULT 0.15 CHECK (resilience_weight >= 0),
    strategic_fit_weight NUMERIC(6,5) NOT NULL DEFAULT 0.10 CHECK (strategic_fit_weight >= 0),
    risk_penalty_weight NUMERIC(6,5) NOT NULL DEFAULT 0.10 CHECK (risk_penalty_weight >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (financial_weight + ecological_weight + social_weight + governance_weight + resilience_weight + strategic_fit_weight = 1)
);

CREATE TABLE IF NOT EXISTS strategy_investment_case (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    objective_id UUID REFERENCES objective(id) ON DELETE SET NULL,
    initiative_id UUID REFERENCES strategy_initiative(id) ON DELETE SET NULL,
    program_id UUID REFERENCES program(id) ON DELETE SET NULL,
    project_id UUID REFERENCES project(id) ON DELETE SET NULL,
    financial_plan_id UUID REFERENCES financial_plan(id) ON DELETE SET NULL,
    budget_line_id UUID REFERENCES budget_line(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    expected_benefit TEXT,
    estimated_cost NUMERIC(15,2) CHECK (estimated_cost IS NULL OR estimated_cost >= 0),
    minimum_viable_funding NUMERIC(15,2) CHECK (minimum_viable_funding IS NULL OR minimum_viable_funding >= 0),
    required_capacity_hours NUMERIC(10,2) CHECK (required_capacity_hours IS NULL OR required_capacity_hours >= 0),
    financial_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (financial_score BETWEEN 0 AND 100),
    ecological_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (ecological_score BETWEEN 0 AND 100),
    social_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (social_score BETWEEN 0 AND 100),
    governance_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (governance_score BETWEEN 0 AND 100),
    resilience_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (resilience_score BETWEEN 0 AND 100),
    strategic_fit_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (strategic_fit_score BETWEEN 0 AND 100),
    risk_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (risk_score BETWEEN 0 AND 100),
    composite_score NUMERIC(6,2),
    dependencies JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'scored', 'recommended', 'approved', 'deferred', 'rejected', 'stopped')),
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategy_allocation_decision (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    selected_investment_ids UUID[] NOT NULL DEFAULT '{}',
    deferred_investment_ids UUID[] NOT NULL DEFAULT '{}',
    rejected_investment_ids UUID[] NOT NULL DEFAULT '{}',
    rationale TEXT NOT NULL,
    resource_impact JSONB NOT NULL DEFAULT '{}',
    decided_by_party_id UUID NOT NULL REFERENCES party(id) ON DELETE RESTRICT,
    decision_status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (decision_status IN ('draft', 'submitted', 'approved', 'superseded')),
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (decision_status <> 'approved' OR decided_at IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_strategy_investment_plan ON strategy_investment_case(strategy_plan_id, status, composite_score DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_investment_links ON strategy_investment_case(objective_id, initiative_id, project_id);
CREATE INDEX IF NOT EXISTS idx_strategy_allocation_decision_plan ON strategy_allocation_decision(strategy_plan_id, decision_status);

DROP TRIGGER IF EXISTS trg_strategy_allocation_policy_updated_at ON strategy_allocation_policy;
CREATE TRIGGER trg_strategy_allocation_policy_updated_at BEFORE UPDATE ON strategy_allocation_policy
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_strategy_investment_updated_at ON strategy_investment_case;
CREATE TRIGGER trg_strategy_investment_updated_at BEFORE UPDATE ON strategy_investment_case
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE strategy_allocation_policy IS 'Composite scoring weights; dimension scores remain visible alongside the optimized score';
COMMENT ON TABLE strategy_investment_case IS 'Strategic investment candidate linking objectives, initiatives, projects, budgets, capacity, benefits, and risk';
COMMENT ON TABLE strategy_allocation_decision IS 'Human-governed selection, deferral, and rejection of strategic investments';
