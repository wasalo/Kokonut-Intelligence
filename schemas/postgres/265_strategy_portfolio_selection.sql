-- ============================================================
-- 265_strategy_portfolio_selection.sql
-- Persisted feasible portfolio selection runs.
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy_portfolio_selection (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    budget_limit NUMERIC(15,2) CHECK (budget_limit IS NULL OR budget_limit >= 0),
    capacity_limit_hours NUMERIC(10,2) CHECK (capacity_limit_hours IS NULL OR capacity_limit_hours >= 0),
    selected_investment_ids UUID[] NOT NULL DEFAULT '{}',
    deferred_investment_ids UUID[] NOT NULL DEFAULT '{}',
    infeasible_investment_ids UUID[] NOT NULL DEFAULT '{}',
    objective_score NUMERIC(12,2) NOT NULL DEFAULT 0,
    used_budget NUMERIC(15,2) NOT NULL DEFAULT 0,
    used_capacity_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    constraint_explanations JSONB NOT NULL DEFAULT '[]',
    status VARCHAR(20) NOT NULL DEFAULT 'recommended'
        CHECK (status IN ('draft', 'recommended', 'approved', 'superseded')),
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status <> 'approved' OR approved_at IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_strategy_portfolio_selection_plan
    ON strategy_portfolio_selection(strategy_plan_id, status, created_at DESC);

COMMENT ON TABLE strategy_portfolio_selection IS 'Optimized feasible investment portfolio under budget, capacity, and dependency constraints';
