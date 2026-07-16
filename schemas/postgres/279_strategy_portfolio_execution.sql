-- ============================================================
-- 279_strategy_portfolio_execution.sql
-- Turn approved strategic selections into reserved execution work.
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy_portfolio_execution (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    selection_id UUID NOT NULL REFERENCES strategy_portfolio_selection(id) ON DELETE CASCADE,
    investment_id UUID NOT NULL REFERENCES strategy_investment_case(id) ON DELETE CASCADE,
    work_item_id UUID REFERENCES work_item(id) ON DELETE SET NULL,
    demand_signal_id UUID REFERENCES operating_demand_signal(id) ON DELETE SET NULL,
    reserved_budget NUMERIC(15,2) NOT NULL DEFAULT 0 CHECK (reserved_budget >= 0),
    reserved_capacity_hours NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (reserved_capacity_hours >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'reserved'
        CHECK (status IN ('reserved', 'released', 'completed', 'cancelled')),
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    released_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (selection_id, investment_id)
);

CREATE INDEX IF NOT EXISTS idx_strategy_portfolio_execution_selection
    ON strategy_portfolio_execution(selection_id, status);
CREATE INDEX IF NOT EXISTS idx_strategy_portfolio_execution_work
    ON strategy_portfolio_execution(work_item_id);

COMMENT ON TABLE strategy_portfolio_execution IS 'Budget and capacity reservations emitted from an approved strategy portfolio';
